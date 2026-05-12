"""Admin 라이브러리 관리 API.

§3.1 — 전용 admin library 엔드포인트 (GET 목록/상세, 빌드 트리거, 빌드 취소).
기존 /api/admin/file-storage/build 는 하위 호환 유지, 이 라우터는 /api/admin/libraries 접두어.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info, require_admin
from app.services import libraries as lib_svc
from app.services import library_builder, manila, neutron
from app.services.keystone import get_service_project_connection

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
    token_info: dict = Depends(get_token_info),
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
            result = await library_builder.queue_build(req.library_id)
            await rec(token_info, None, resource_type="library", action="build", resource_id=req.library_id)
            return result
        except RuntimeError as e:
            await rec(
                token_info,
                None,
                resource_type="library",
                action="build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
            status_code = 409 if "이미" in str(e) else 400
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
            await rec(token_info, None, resource_type="library", action="prebuilt_build", resource_id=req.library_id)
            return {
                "file_storage_id": storage.id,
                "status": "pending",
                "library": req.library_id,
                "message": "빈 share 생성 완료. 수동으로 패키지를 설치하세요.",
            }
        except RuntimeError as e:
            await rec(
                token_info,
                None,
                resource_type="library",
                action="prebuilt_build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            _logger.warning("Share 생성 실패: %s", e)
            await rec(
                token_info,
                None,
                resource_type="library",
                action="prebuilt_build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
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


# ---------------------------------------------------------------------------
# NFS 크로스 프로젝트 access rule 관리 (§3.3)
# ---------------------------------------------------------------------------


class GrantProjectAccessRequest(BaseModel):
    project_id: str
    network_id: str


def _get_nfs_share_for_library(conn, library_id: str):
    """라이브러리 ID로 prebuilt NFS share를 조회. NFS가 아니거나 없으면 예외."""
    try:
        lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}를 찾을 수 없습니다")

    storages = manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt", "union_library": library_id})
    if not storages:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}의 prebuilt share가 없습니다")
    storage = storages[0]
    if storage.share_proto != "NFS":
        raise HTTPException(
            status_code=400,
            detail=f"라이브러리 {library_id}는 NFS가 아닙니다 (proto={storage.share_proto}). IP access rule이 필요하지 않습니다.",
        )
    return storage


@router.post("/{library_id}/project-access", dependencies=[Depends(require_admin)])
async def grant_library_project_access(
    library_id: str,
    req: GrantProjectAccessRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """NFS prebuilt 라이브러리에 특정 프로젝트의 subnet CIDR access rule을 추가한다.

    이미 rule이 있으면 idempotent하게 처리한다 (중복 생성 없음).
    """
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        net_detail = await asyncio.to_thread(neutron.get_network_detail, conn, req.network_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"네트워크 CIDR 조회 실패: {e}")

    cidrs = [s.cidr for s in (net_detail.subnet_details or []) if s.cidr]
    if not cidrs:
        raise HTTPException(status_code=400, detail="해당 네트워크에 subnet CIDR이 없습니다")

    granted = []
    for cidr in cidrs:
        try:
            rule = await asyncio.to_thread(
                manila.ensure_nfs_access_rule,
                svc_conn,
                storage.id,
                cidr,
                "ro",
                True,
                "sys",
                {"union_grant_project": req.project_id},
            )
            granted.append({"cidr": cidr, "rule_id": rule["access_id"]})
        except Exception as e:
            _logger.error("NFS access rule 추가 실패 (cidr=%s): %s", cidr, e)
            raise HTTPException(status_code=502, detail=f"NFS access rule 추가 실패 (cidr={cidr}): {e}")

    await rec(
        token_info,
        conn,
        resource_type="library",
        action="link",
        resource_id=library_id,
        extra={"project_id": req.project_id},
    )
    return {
        "library_id": library_id,
        "share_id": storage.id,
        "project_id": req.project_id,
        "granted_cidrs": [g["cidr"] for g in granted],
        "rules": granted,
    }


@router.delete("/{library_id}/project-access/{project_id}", dependencies=[Depends(require_admin)])
async def revoke_library_project_access(
    library_id: str,
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """NFS prebuilt 라이브러리에서 특정 프로젝트의 CIDR access rule을 revoke한다.

    union_grant_project metadata로 해당 프로젝트의 rule을 식별한다.
    """
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        access_rules = await asyncio.to_thread(manila.list_access_rules, svc_conn, storage.id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"access rule 목록 조회 실패: {e}")

    target_rules = [
        r
        for r in access_rules
        if r.get("access_type") == "ip" and r.get("metadata", {}).get("union_grant_project") == project_id
    ]

    revoked_ids = []
    for rule in target_rules:
        try:
            await asyncio.to_thread(manila.revoke_access_rule, svc_conn, storage.id, rule["id"])
            revoked_ids.append(rule["id"])
        except Exception as e:
            _logger.error("NFS access rule revoke 실패 (rule=%s): %s", rule["id"], e)
            raise HTTPException(status_code=502, detail=f"access rule revoke 실패 (rule_id={rule['id']}): {e}")

    await rec(
        token_info,
        conn,
        resource_type="library",
        action="unlink",
        resource_id=library_id,
        extra={"project_id": project_id},
    )
    return {
        "library_id": library_id,
        "share_id": storage.id,
        "project_id": project_id,
        "revoked_count": len(revoked_ids),
        "revoked_rule_ids": revoked_ids,
    }


@router.get("/{library_id}/project-access", dependencies=[Depends(require_admin)])
async def list_library_project_access(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> dict:
    """NFS prebuilt 라이브러리에 grant된 프로젝트별 CIDR access rule 목록을 반환한다."""
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        access_rules = await asyncio.to_thread(manila.list_access_rules, svc_conn, storage.id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"access rule 목록 조회 실패: {e}")

    # union_grant_project metadata로 프로젝트별 grouping
    grants: dict[str, dict] = {}
    for rule in access_rules:
        if rule.get("access_type") != "ip":
            continue
        pid = rule.get("metadata", {}).get("union_grant_project", "__unknown__")
        if pid not in grants:
            grants[pid] = {"project_id": pid, "cidrs": [], "rule_ids": []}
        grants[pid]["cidrs"].append(rule.get("access_to", ""))
        grants[pid]["rule_ids"].append(rule["id"])

    return {
        "library_id": library_id,
        "share_id": storage.id,
        "grants": list(grants.values()),
    }
