"""Admin orphan resource detection API.

운영 중 단계적 실패로 누적되는 고아 리소스(분리된 FIP, 장기 미사용 volume)를
한 화면에서 검색하고 안전하게 일괄 정리한다. 모든 작업은 admin 전용.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info, require_admin
from app.models.orphans import (
    OrphanCleanupRequest,
    OrphanCleanupResponse,
    OrphanScanResponse,
)
from app.services import orphans

if TYPE_CHECKING:
    import openstack

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/orphans",
    response_model=OrphanScanResponse,
    dependencies=[Depends(require_admin)],
)
async def list_orphans(
    min_age_days: int = Query(14, ge=1, le=365),
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> OrphanScanResponse:
    """admin 전(全) 프로젝트 범위에서 orphan 후보를 반환."""
    return OrphanScanResponse(
        floating_ips=orphans.find_orphan_floating_ips(conn),
        volumes=orphans.find_orphan_volumes(conn, min_age_days),
    )


@router.post(
    "/orphans/cleanup",
    response_model=OrphanCleanupResponse,
    dependencies=[Depends(require_admin)],
)
async def cleanup_orphans(
    req: OrphanCleanupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> OrphanCleanupResponse:
    """주어진 ID 목록을 일괄 정리. race-safe 검증 + 각 결과를 audit log 기록."""
    if req.kind == "floating_ip":
        deleted, failed = orphans.cleanup_floating_ips(conn, req.ids)
    else:  # "volume"
        deleted, failed = orphans.cleanup_volumes(conn, req.ids)

    for rid in deleted:
        await rec(
            token_info,
            conn,
            resource_type=req.kind,
            action="orphan.cleanup",
            resource_id=rid,
            status="success",
        )
    for f in failed:
        await rec(
            token_info,
            conn,
            resource_type=req.kind,
            action="orphan.cleanup",
            resource_id=f.get("id"),
            status="failed",
            error_message=f.get("error"),
        )

    return OrphanCleanupResponse(deleted=deleted, failed=failed)
