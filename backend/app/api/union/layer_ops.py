"""squashfs NFS 레이어 빌드/소비 관리 API.

/api/admin/layers 접두사로 마운트. 전 엔드포인트 require_admin.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import desc, select

from app.api.deps import require_admin
from app.database import get_session_factory

_logger = logging.getLogger(__name__)


def _iso(dt: datetime | None) -> str | None:
    """datetime → ISO 8601 문자열. naive datetime은 UTC로 간주하고 'Z' suffix 부착."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")

router = APIRouter()

# ---------------------------------------------------------------------------
# 입력 모델 (Pydantic 화이트리스트 validator)
# ---------------------------------------------------------------------------

_LAYER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]*$")
_PY_VERSION_RE = re.compile(r"^\d+\.\d+$")
_PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\[\],<>=!~+*\-]*$")
_SERVER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_.]*$")
_FLAVOR_ID_RE = re.compile(r"^[a-zA-Z0-9\-_.]+$")


class LayerBuildRequest(BaseModel):
    """레이어 빌드 요청 — base 또는 stacked 레이어 빌드."""

    layer_name: str
    # "uv" | "python" | 기타 사용자 정의 kind (pip, torch 등)
    kind: str = "python"
    # kind="python"일 때만 필수 (stacked 빌드 시 부모의 uv로 설치하므로 필수)
    python_version: str | None = None
    pip_packages: list[str] = []
    # 부모 레이어 이름 — 지정 시 stacked 빌드 (부모 체인 RO 마운트 → delta squash)
    parent: str | None = None

    @field_validator("layer_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _LAYER_NAME_RE.match(v):
            raise ValueError(f"유효하지 않은 이름 (소문자·숫자·점·하이픈만 허용): {v!r}")
        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if not _LAYER_NAME_RE.match(v):
            raise ValueError(f"유효하지 않은 kind (소문자·숫자·점·하이픈만 허용): {v!r}")
        return v

    @field_validator("parent")
    @classmethod
    def validate_parent(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _LAYER_NAME_RE.match(v):
            raise ValueError(f"유효하지 않은 부모 레이어 이름: {v!r}")
        return v

    @field_validator("python_version")
    @classmethod
    def validate_python_version(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _PY_VERSION_RE.match(v):
            raise ValueError(f"유효하지 않은 Python 버전 (예: '3.11'): {v!r}")
        return v

    @field_validator("pip_packages", mode="before")
    @classmethod
    def validate_pip_packages(cls, v: list) -> list:
        for pkg in v:
            if not _PIP_SPEC_RE.match(str(pkg)):
                raise ValueError(f"유효하지 않은 pip 스펙: {pkg!r}")
        return v

    @model_validator(mode="after")
    def validate_kind_requirements(self) -> LayerBuildRequest:
        if self.kind == "uv" and self.python_version is not None:
            raise ValueError("kind='uv'일 때 python_version은 사용할 수 없습니다")
        if self.kind == "python" and not self.python_version and not self.parent:
            raise ValueError("kind='python'일 때 python_version은 필수입니다 (stacked 빌드 시 parent 지정 가능)")
        return self


class LayerConsumeRequest(BaseModel):
    """레이어 소비 인스턴스 생성 요청."""

    profile_name: str
    server_name: str
    flavor_id: str
    image_id: str | None = None
    network_id: str | None = None

    @field_validator("profile_name")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        if not _LAYER_NAME_RE.match(v):
            raise ValueError(f"유효하지 않은 프로필 이름: {v!r}")
        return v

    @field_validator("server_name")
    @classmethod
    def validate_server_name(cls, v: str) -> str:
        if not _SERVER_NAME_RE.match(v) or len(v) > 63:
            raise ValueError(f"유효하지 않은 서버 이름: {v!r}")
        return v

    @field_validator("flavor_id")
    @classmethod
    def validate_flavor_id(cls, v: str) -> str:
        if not _FLAVOR_ID_RE.match(v):
            raise ValueError(f"유효하지 않은 flavor_id: {v!r}")
        return v


class LayerProfileRequest(BaseModel):
    """레이어 프로필 구성 요청 — 여러 레이어를 묶어 named 프로필로 저장."""

    name: str
    layers: list[str]  # 순서 있는 레이어 이름 리스트 (OverlayFS lowerdir 위→아래)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _LAYER_NAME_RE.match(v):
            raise ValueError(f"유효하지 않은 프로필 이름: {v!r}")
        return v

    @field_validator("layers", mode="before")
    @classmethod
    def validate_layers(cls, v: list) -> list:
        if not v:
            raise ValueError("layers는 최소 1개 이상이어야 합니다")
        for layer in v:
            if not _LAYER_NAME_RE.match(str(layer)):
                raise ValueError(f"유효하지 않은 레이어 이름: {layer!r}")
        return v


# ---------------------------------------------------------------------------
# 빌드 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/build", dependencies=[Depends(require_admin)])
async def trigger_layer_build(req: LayerBuildRequest) -> dict:
    """squashfs 레이어 빌드를 시작한다. 백그라운드 태스크로 실행.

    parent 지정 시 stacked 빌드: 부모 체인 share를 RO 마운트 → delta squash.
    """
    from app.models.db import LayerArtifact
    from app.services import layer_builder

    _logger.info(
        "[layer_ops] 빌드 요청: layer=%s kind=%s python=%s parent=%s pip_count=%d",
        req.layer_name, req.kind, req.python_version or "-",
        req.parent or "-", len(req.pip_packages or []),
    )

    # 부모 레이어 이름을 artifact ID로 변환
    parent_artifact_id: int | None = None
    if req.parent:
        async with get_session_factory()() as session:
            parent_row = (
                await session.execute(
                    select(LayerArtifact)
                    .where(LayerArtifact.name == req.parent)
                    .where(LayerArtifact.is_sealed.is_(True))
                    .order_by(desc(LayerArtifact.id))
                    .limit(1)
                )
            ).scalar_one_or_none()
        if parent_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"부모 레이어 {req.parent!r}를 찾을 수 없습니다 (봉인된 artifact 필요)",
            )
        parent_artifact_id = parent_row.id

    result = await layer_builder.start_layer_build(
        layer_name=req.layer_name,
        kind=req.kind,
        python_version=req.python_version,
        pip_packages=req.pip_packages,
        parent_artifact_id=parent_artifact_id,
    )
    _logger.info("[layer_ops] 빌드 등록 완료: build_id=%s layer=%s", result.get("build_id"), req.layer_name)
    return result


@router.get("/builds", dependencies=[Depends(require_admin)])
async def list_layer_builds(limit: int = 50) -> list[dict]:
    """최근 레이어 빌드 목록 (최대 50건). 모니터링용."""
    from app.models.db import LayerBuild

    async with get_session_factory()() as session:
        rows = (
            (await session.execute(select(LayerBuild).order_by(desc(LayerBuild.created_at)).limit(min(limit, 100))))
            .scalars()
            .all()
        )

    return [_build_row_to_dict(r) for r in rows]


@router.get("/builds/{build_id}", dependencies=[Depends(require_admin)])
async def get_layer_build(build_id: int) -> dict:
    """빌드 상세 + 라이브 VM 상태 + 콘솔 로그."""
    import asyncio

    from app.models.db import LayerBuild
    from app.services import nova
    from app.services.keystone import get_service_project_connection

    async with get_session_factory()() as session:
        row = (await session.execute(select(LayerBuild).where(LayerBuild.id == build_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"빌드 {build_id}를 찾을 수 없습니다")

    result = _build_row_to_dict(row)

    # 진행 중인 빌드의 경우 라이브 VM 상태 + 콘솔 조회
    if row.server_id and row.status not in {"complete", "error", "cancelled"}:
        try:
            conn = await asyncio.to_thread(get_service_project_connection)
            server = await asyncio.to_thread(conn.compute.get_server, row.server_id)
            result["vm_status"] = server.status
            result["vm_ip"] = next(
                (addr["addr"] for addrs in (server.addresses or {}).values() for addr in addrs),
                None,
            )
            try:
                result["live_console"] = await asyncio.to_thread(nova.get_console_output, conn, row.server_id, 200)
            except Exception:
                result["live_console"] = None
        except Exception:
            _logger.debug("[layer_ops] VM 상태 조회 실패: server=%s", row.server_id)

    return result


@router.post("/builds/{build_id}/cancel", dependencies=[Depends(require_admin)])
async def cancel_layer_build(build_id: int) -> dict:
    """진행 중인 레이어 빌드를 취소한다."""
    from app.services import layer_builder

    _logger.info("[layer_ops] 빌드 취소 요청: build_id=%d", build_id)
    try:
        result = await layer_builder.cancel_layer_build(build_id)
        _logger.info("[layer_ops] 빌드 취소 완료: build_id=%d", build_id)
        return result
    except KeyError as e:
        _logger.warning("[layer_ops] 빌드 취소 실패 — not found: build_id=%d", build_id)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        _logger.warning("[layer_ops] 빌드 취소 실패 — 상태 불일치: build_id=%d err=%s", build_id, e)
        raise HTTPException(status_code=409, detail=str(e)) from e


# ---------------------------------------------------------------------------
# 소비 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/consume", dependencies=[Depends(require_admin)])
async def trigger_layer_consume(req: LayerConsumeRequest) -> dict:
    """레이어 소비 인스턴스를 생성한다.

    layer-store-ro NFS share를 RO 마운트하고 layer-activate.sh로
    squashfs + OverlayFS를 활성화하는 VM을 생성해 반환한다.
    """
    _logger.info(
        "[layer_ops] 소비 인스턴스 요청: profile=%s server_name=%s flavor=%s",
        req.profile_name, req.server_name, req.flavor_id,
    )

    from app.config import get_settings
    from app.database import get_session_factory
    from app.models.db import LayerConsume
    from app.services.layer_build import run_layer_consume

    settings = get_settings()
    ro_share_id = settings.union_layer_store_ro_share_id or ""

    # DB 레코드 생성
    consume_db_id: int | None = None
    factory = get_session_factory()
    if factory:
        async with factory() as session:
            row = LayerConsume(
                profile_name=req.profile_name,
                server_name=req.server_name,
                share_id=ro_share_id,
                status="creating",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            consume_db_id = row.id

    try:
        server_id = await run_layer_consume(
            consume_db_id=consume_db_id,
            profile_name=req.profile_name,
            server_name=req.server_name,
            flavor_id=req.flavor_id,
            image_id=req.image_id,
            network_id=req.network_id,
        )
        return {"consume_id": consume_db_id, "server_id": server_id, "status": "active"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/consumes", dependencies=[Depends(require_admin)])
async def list_layer_consumes(limit: int = 50) -> list[dict]:
    """최근 소비 인스턴스 목록 (최대 50건)."""
    from app.models.db import LayerConsume

    async with get_session_factory()() as session:
        rows = (
            (await session.execute(select(LayerConsume).order_by(desc(LayerConsume.created_at)).limit(min(limit, 100))))
            .scalars()
            .all()
        )

    return [_consume_row_to_dict(r) for r in rows]


@router.get("/consumes/{consume_id}", dependencies=[Depends(require_admin)])
async def get_layer_consume(consume_id: int) -> dict:
    """소비 인스턴스 상세 + 라이브 Nova 상태."""
    import asyncio

    from app.models.db import LayerConsume
    from app.services.keystone import get_service_project_connection

    async with get_session_factory()() as session:
        row = (await session.execute(select(LayerConsume).where(LayerConsume.id == consume_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"소비 인스턴스 {consume_id}를 찾을 수 없습니다")

    result = _consume_row_to_dict(row)

    if row.server_id:
        try:
            conn = await asyncio.to_thread(get_service_project_connection)
            server = await asyncio.to_thread(conn.compute.get_server, row.server_id)
            result["vm_status"] = server.status
            result["vm_ip"] = next(
                (addr["addr"] for addrs in (server.addresses or {}).values() for addr in addrs),
                None,
            )
        except Exception:
            _logger.debug("[layer_ops] 소비 VM 상태 조회 실패: server=%s", row.server_id)

    return result


# ---------------------------------------------------------------------------
# 아티팩트 엔드포인트
# ---------------------------------------------------------------------------


@router.get("/artifacts", dependencies=[Depends(require_admin)])
async def list_layer_artifacts(limit: int = 100) -> list[dict]:
    """빌드된 레이어 아티팩트 목록 — 프로필 구성 폼에서 선택지로 사용."""
    from app.models.db import LayerArtifact

    async with get_session_factory()() as session:
        rows = (
            (
                await session.execute(
                    select(LayerArtifact).order_by(desc(LayerArtifact.created_at)).limit(min(limit, 200))
                )
            )
            .scalars()
            .all()
        )

    return [_artifact_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 프로필 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/profiles", dependencies=[Depends(require_admin)])
async def upsert_layer_profile(req: LayerProfileRequest) -> dict:
    """레이어 프로필을 생성하거나 갱신한다 (upsert).

    layers 리스트의 각 레이어가 LayerArtifact에 존재해야 한다.
    """
    _logger.info("[layer_ops] 프로필 upsert: name=%s layers=%s", req.name, req.layers)
    from app.models.db import LayerArtifact, LayerProfile

    async with get_session_factory()() as session:
        # 각 레이어 존재 여부 검증
        art_rows = (await session.execute(select(LayerArtifact.name).distinct())).scalars().all()
        existing_names: set[str] = set(art_rows)

        missing = [layer for layer in req.layers if layer not in existing_names]
        if missing:
            from fastapi import HTTPException as _HTTPException

            raise _HTTPException(
                status_code=400,
                detail=f"존재하지 않는 레이어: {missing}. 먼저 빌드하세요.",
            )

        # upsert
        existing = (
            await session.execute(select(LayerProfile).where(LayerProfile.name == req.name))
        ).scalar_one_or_none()

        if existing:
            existing.layers = req.layers
            profile = existing
        else:
            profile = LayerProfile(name=req.name, layers=req.layers)
            session.add(profile)

        await session.commit()
        await session.refresh(profile)

    return _profile_row_to_dict(profile)


@router.get("/profiles", dependencies=[Depends(require_admin)])
async def list_layer_profiles() -> list[dict]:
    """저장된 레이어 프로필 목록."""
    from app.models.db import LayerProfile

    async with get_session_factory()() as session:
        rows = (await session.execute(select(LayerProfile).order_by(LayerProfile.name))).scalars().all()

    return [_profile_row_to_dict(r) for r in rows]


@router.get("/profiles/{profile_name}", dependencies=[Depends(require_admin)])
async def get_layer_profile(profile_name: str) -> dict:
    """레이어 프로필 상세."""
    from app.models.db import LayerProfile

    async with get_session_factory()() as session:
        row = (
            await session.execute(select(LayerProfile).where(LayerProfile.name == profile_name))
        ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"프로필 '{profile_name}'을 찾을 수 없습니다")

    return _profile_row_to_dict(row)


# ---------------------------------------------------------------------------
# 직렬화 헬퍼
# ---------------------------------------------------------------------------


def _build_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "layer_name": row.layer_name,
        "python_version": row.python_version,
        "profile_name": row.profile_name,
        "share_id": row.share_id,
        "server_id": row.server_id,
        "port_id": row.port_id,
        "build_token": row.build_token,
        "cloud_init_status": row.cloud_init_status,
        "status": row.status,
        "progress_step": row.progress_step,
        "progress_pct": row.progress_pct,
        "error_message": row.error_message,
        "console_log_excerpt": row.console_log_excerpt,
        "started_at": _iso(row.started_at),
        "completed_at": _iso(row.completed_at),
        "created_at": _iso(row.created_at),
    }


def _consume_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "profile_name": row.profile_name,
        "server_id": row.server_id,
        "port_id": row.port_id,
        "server_name": row.server_name,
        "share_id": row.share_id,
        "status": row.status,
        "error_message": row.error_message,
        "created_at": _iso(row.created_at),
        "completed_at": _iso(row.completed_at),
    }


def _artifact_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "python_version": row.python_version,
        "sqsh_filename": row.sqsh_filename,
        "share_id": row.share_id,
        "build_id": row.build_id,
        "size_bytes": row.size_bytes,
        "parent_id": row.parent_id,
        "is_sealed": row.is_sealed,
        "created_at": _iso(row.created_at),
    }


def _profile_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "layers": row.layers,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
