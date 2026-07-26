"""Palimpsest 관리자 API — digest 백필과 전체 레이어 조회."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import require_admin
from app.api.palimpsest.layers import _layer_dict
from app.database import get_session_factory
from app.models.db import LayerArtifact
from app.services.cache import invalidate
from app.services.palimpsest_backfill import BackfillError, backfill_digests

_logger = logging.getLogger(__name__)

router = APIRouter()


class BackfillDigestRequest(BaseModel):
    limit: int = Field(20, ge=1, le=100, description="이번 배치에서 처리할 artifact 수")
    retry_failed: bool = Field(False, description="이전에 digest_state='failed' 로 남은 건도 재시도")


@router.get("/artifacts", dependencies=[Depends(require_admin)])
async def list_all_artifacts() -> list[dict[str, Any]]:
    """공개 여부와 무관한 전체 레이어 목록(digest 필드 포함)."""
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="DB 연결이 초기화되지 않았습니다")
    async with factory() as session:
        rows = (await session.execute(select(LayerArtifact).order_by(LayerArtifact.id))).scalars().all()
        return [_layer_dict(row) for row in rows]


@router.get("/digest-status", dependencies=[Depends(require_admin)])
async def digest_status() -> dict[str, Any]:
    """`digest_state` 분포 — 백필이 필요한지 한눈에 보기 위한 요약."""
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="DB 연결이 초기화되지 않았습니다")
    async with factory() as session:
        rows = await session.execute(
            select(LayerArtifact.digest_state, func.count()).group_by(LayerArtifact.digest_state)
        )
        counts = {state: count for state, count in rows}
    return {"counts": counts, "total": sum(counts.values())}


@router.post("/artifacts/backfill-digest", dependencies=[Depends(require_admin)])
async def backfill_digest(req: BackfillDigestRequest) -> dict[str, Any]:
    """기존 artifact 의 blob digest 를 임시 Builder VM 경유로 채운다.

    OpenStack 리소스(임시 VM + Manila access rule)를 쓰므로 배치 단위로 호출한다.
    한 건이 실패해도 나머지는 진행되며, 실패 건은 `digest_state='failed'` 로 남는다.
    """
    try:
        result = await backfill_digests(limit=req.limit, retry_failed=req.retry_failed)
        if result["updated"] or result["chain_updated"]:
            # artifact 응답에 digest/chain_id 가 실리므로 레이어 캐시를 무효화한다
            # (`layer_ops` 가 publication/profile 변경 시 쓰는 것과 같은 네임스페이스).
            await invalidate("afterglow:union_layer:*")
        return result
    except BackfillError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        _logger.exception("[palimpsest_admin] 백필 실패")
        raise HTTPException(status_code=500, detail="digest 백필에 실패했습니다") from exc
