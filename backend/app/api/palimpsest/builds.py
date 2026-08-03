"""Palimpsest 빌드 API — 사용자가 올린 Dockerfile 로 레이어 체인을 만든다.

기존 `/api/v1/admin/libraries/imports/dockerfile` 은 canonical public GitHub repo 의
commit 을 고정해 받아오는 경로다. 여기는 **본문을 직접 올리는** 경로다.

🔴 **보안**: inline Dockerfile 의 `RUN` 은 임의 셸 명령이다. 실행은 격리된 임시 Builder VM
안에서만 일어나고 모든 보간이 `shlex.quote` 되지만, 그럼에도 **관리자 전용**으로 유지한다.
일반 사용자 개방은 격리 강도·쿼터·네트워크 정책이 선행되어야 하는 별도 결정이다.

빌드 컨텍스트가 없으므로 `COPY`/`ADD` 는 거부한다(파서가 `allow_build_context=False`).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_os_conn, require_admin
from app.services.dockerfile_import import (
    DockerfileImportError,
    compute_step_digest,
    create_import_job,
    prepare_inline_dockerfile_import,
)

_logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_DOCKERFILE_CHARS = 1024 * 1024


class InlineDockerfileBuildRequest(BaseModel):
    """업로드한 Dockerfile 로 레이어 체인을 빌드한다."""

    dockerfile: str = Field(..., min_length=1, max_length=_MAX_DOCKERFILE_CHARS)
    layer_prefix: str
    profile_name: str | None = None
    # `FROM ubuntu:<ver>` 일 때 필수. `FROM palimpsest/<name>@sha256:…` 이면 부모에게서 상속한다.
    base_image_id: str | None = None

    @field_validator("dockerfile")
    @classmethod
    def _check_dockerfile(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Dockerfile 본문이 비어 있습니다")
        return value


@router.post("/dockerfile", dependencies=[Depends(require_admin)])
async def build_from_inline_dockerfile(
    req: InlineDockerfileBuildRequest,
    conn=Depends(get_os_conn),
) -> dict[str, Any]:
    """Dockerfile 을 해석해 빌드 잡을 만든다.

    같은 부모 위에 같은 명령이 이미 빌드돼 있으면 그 접두부는 **재사용**하고 나머지만 빌드한다
    (`step_digest` 기반 캐시). 전부 캐시에 맞으면 만들 게 없다는 뜻이므로 409 를 준다.
    """
    try:
        plan = await prepare_inline_dockerfile_import(
            conn,
            dockerfile_text=req.dockerfile,
            layer_prefix=req.layer_prefix,
            profile_name=req.profile_name,
            base_image_id=req.base_image_id,
        )
    except DockerfileImportError as exc:
        message = str(exc)
        # "전부 캐시" 는 잘못된 요청이 아니라 상태 충돌이다
        status = 409 if "모든 단계가 이미 빌드" in message else 422
        raise HTTPException(status_code=status, detail=message) from exc

    try:
        job = await create_import_job(plan)
    except DockerfileImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        **job,
        "source_type": plan.source_type,
        "dockerfile_digest": plan.dockerfile_digest,
        "parent_digest": plan.parent_digest,
        "cached_artifact_ids": plan.cached_artifact_ids,
        "planned_step_count": len(plan.planned_layers),
    }


@router.post("/dockerfile/plan", dependencies=[Depends(require_admin)])
async def preview_inline_dockerfile_plan(
    req: InlineDockerfileBuildRequest,
    conn=Depends(get_os_conn),
) -> dict[str, Any]:
    """빌드하지 않고 계획만 본다 — 어떤 단계가 캐시에 맞는지 확인하는 용도."""
    try:
        plan = await prepare_inline_dockerfile_import(
            conn,
            dockerfile_text=req.dockerfile,
            layer_prefix=req.layer_prefix,
            profile_name=req.profile_name,
            base_image_id=req.base_image_id,
        )
    except DockerfileImportError as exc:
        message = str(exc)
        status = 409 if "모든 단계가 이미 빌드" in message else 422
        raise HTTPException(status_code=status, detail=message) from exc

    return {
        "source_type": plan.source_type,
        "dockerfile_digest": plan.dockerfile_digest,
        "parent_digest": plan.parent_digest,
        "ubuntu_base": plan.base_image_snapshot.get("ubuntu_base"),
        "cached_artifact_ids": plan.cached_artifact_ids,
        "steps": [
            {
                "name": step["name"],
                "instruction": step["instruction"],
                "args": step["args"],
                "step_digest": step.get("step_digest"),
            }
            for step in plan.planned_layers
        ],
    }


__all__ = ["compute_step_digest", "router"]
