"""Admin 라이브러리 관리 API.

§3.1 — 전용 admin library 엔드포인트 (GET 목록/상세, 빌드 트리거, 빌드 취소).
기존 /api/admin/file-storage/build 는 하위 호환 유지, 이 라우터는 /api/admin/libraries 접두어.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn, require_admin
from app.services import libraries as lib_svc
from app.services import library_builder, manila

_logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# 라이브러리 목록 / 상세
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(require_admin)])
async def list_admin_libraries(
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> list[dict]:
    """전체 라이브러리 카탈로그 (의존성, 가용 prebuilt 포함). 관리자 전용."""
    all_libs = lib_svc.get_all()

    try:
        prebuilt_storages = manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt"})
        prebuilt_map = {s.library_name: s for s in prebuilt_storages if s.library_name}
    except Exception:
        prebuilt_map = {}

    result = []
    for lib in all_libs:
        storage = prebuilt_map.get(lib.id)
        result.append(
            {
                "id": lib.id,
                "name": lib.name,
                "version": lib.version,
                "packages": lib.packages,
                "depends_on": lib.depends_on,
                "visibility": lib.visibility,
                "share_proto": lib.share_proto,
                "ubuntu_versions": lib.ubuntu_versions,
                "file_storage_id": storage.id if storage else None,
                "available_prebuilt": storage is not None,
                "build_status": (storage.metadata.get("union_status") if storage else None),
                "built_at": (storage.built_at if storage else None),
                "dependency_tree": lib_svc.get_dependency_tree(lib.id),
            }
        )
    return result


@router.get("/builds", dependencies=[Depends(require_admin)])
async def list_library_builds(
    library_id: str | None = Query(default=None),
) -> list[dict]:
    """라이브러리 빌드 이력 목록. 관리자 전용."""
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        # DB 미초기화 시 인메모리 캐시 반환
        builds = list(library_builder.get_active_builds().values())
        if library_id:
            builds = [b for b in builds if b.get("library_id") == library_id]
        return builds

    async with factory() as session:
        stmt = select(LibraryBuild).order_by(LibraryBuild.started_at.desc()).limit(50)
        if library_id:
            stmt = stmt.where(LibraryBuild.library_id == library_id)
        rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": row.id,
            "library_id": row.library_id,
            "file_storage_id": row.file_storage_id,
            "server_id": row.server_id,
            "status": row.status,
            "progress_step": row.progress_step,
            "progress_pct": row.progress_pct,
            "error_message": row.error_message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]


@router.get("/{library_id}", dependencies=[Depends(require_admin)])
async def get_admin_library(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> dict:
    """라이브러리 상세 (의존성 트리 + prebuilt 상태 포함). 관리자 전용."""
    try:
        lib = lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}를 찾을 수 없습니다")

    try:
        storages = manila.list_file_storages(
            conn, metadata_filter={"union_type": "prebuilt", "union_library": library_id}
        )
        storage = storages[0] if storages else None
    except Exception:
        storage = None

    return {
        "id": lib.id,
        "name": lib.name,
        "version": lib.version,
        "packages": lib.packages,
        "depends_on": lib.depends_on,
        "visibility": lib.visibility,
        "share_proto": lib.share_proto,
        "ubuntu_versions": lib.ubuntu_versions,
        "file_storage_id": storage.id if storage else None,
        "available_prebuilt": storage is not None,
        "build_status": (storage.metadata.get("union_status") if storage else None),
        "built_at": (storage.built_at if storage else None),
        "dependency_tree": lib_svc.get_dependency_tree(library_id),
        "active_builds": library_builder.get_active_builds().get(library_id),
    }


# ---------------------------------------------------------------------------
# 빌드 트리거
# ---------------------------------------------------------------------------


class TriggerBuildRequest(BaseModel):
    library_id: str
    auto_install: bool = True


@router.post("/build", status_code=202, dependencies=[Depends(require_admin)])
async def trigger_library_build(
    req: TriggerBuildRequest,
) -> dict:
    """라이브러리 prebuilt 빌드 트리거. auto_install=True 시 Builder VM 자동 생성.

    Manila share와 빌더 VM은 service 프로젝트에 생성된다.
    """
    try:
        lib_svc.get_by_id(req.library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {req.library_id}를 찾을 수 없습니다")

    if req.auto_install:
        try:
            result = await library_builder.start_build(req.library_id)
            return result
        except RuntimeError as e:
            status_code = 409 if "이미 빌드 중" in str(e) else 400
            raise HTTPException(status_code=status_code, detail=str(e))
    else:
        # auto_install=False: 빈 share 생성만 수행 (수동 설치용) — service 프로젝트에 생성
        import asyncio

        from app.config import get_settings
        from app.services.keystone import get_service_project_connection

        settings = get_settings()
        lib = lib_svc.get_by_id(req.library_id)
        try:
            svc_conn = await asyncio.to_thread(get_service_project_connection)
            storage = await asyncio.to_thread(
                manila.create_file_storage,
                svc_conn,
                name=f"union-prebuilt-{req.library_id}",
                size_gb=20,
                share_network_id=settings.os_manila_share_network_id,
                share_type=settings.os_manila_share_type,
                metadata={
                    "union_type": "prebuilt",
                    "union_library": req.library_id,
                    "union_version": lib.version,
                    "union_status": "pending",
                },
            )
            return {
                "file_storage_id": storage.id,
                "status": "pending",
                "library": req.library_id,
                "message": "빈 share 생성 완료. 수동으로 패키지를 설치하세요.",
            }
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            _logger.warning("Share 생성 실패: %s", e)
            raise HTTPException(status_code=502, detail="Share 생성 실패")


# ---------------------------------------------------------------------------
# 빌드 취소
# ---------------------------------------------------------------------------


@router.post("/builds/{build_id}/cancel", dependencies=[Depends(require_admin)])
async def cancel_library_build(
    build_id: int,
) -> dict:
    """진행 중인 라이브러리 빌드를 취소하고 VM 리소스를 정리한다. 관리자 전용."""
    try:
        return await library_builder.cancel_build(build_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
