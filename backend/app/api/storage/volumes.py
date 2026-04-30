from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_os_conn, require_admin
from app.models.storage import CreateVolumeRequest, VolumeInfo
from app.rate_limit import limiter
from app.services import cinder, nova
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("", response_model=list[VolumeInfo])
async def list_volumes(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:cinder:{pid}:volumes",
            ttl_fast(),
            lambda: [v.model_dump() for v in cinder.list_volumes(conn)],
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 목록 조회 실패")


@router.get("/{volume_id}", response_model=VolumeInfo)
async def get_volume(volume_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(cinder.get_volume, conn, volume_id)
    except Exception:
        raise HTTPException(status_code=404, detail="볼륨을 찾을 수 없습니다")


@router.post("", response_model=VolumeInfo, status_code=201)
@limiter.limit("10/minute")
async def create_volume(
    request: Request,
    req: CreateVolumeRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(cinder.create_empty_volume, conn, req.name, req.size_gb, req.availability_zone)
        await invalidate(f"afterglow:cinder:{pid}:volumes")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 생성 실패")


@router.delete("/{volume_id}", status_code=204)
async def delete_volume(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(cinder.delete_volume, conn, volume_id)
        await invalidate(f"afterglow:cinder:{pid}:volumes")
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 삭제 실패")


@router.post("/{volume_id}/force-delete", status_code=204)
async def force_delete_volume(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    _: None = Depends(require_admin),
):
    """error/error_deleting 상태 볼륨을 강제 삭제한다. 관리자 전용."""
    pid = conn._afterglow_project_id
    try:
        # reset_status → error 상태로 전환 후 force delete
        await asyncio.to_thread(cinder.reset_volume_status, conn, volume_id, "error")
        await asyncio.to_thread(cinder.force_delete_volume, conn, volume_id)
        await invalidate(f"afterglow:cinder:{pid}:volumes")
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 강제 삭제 실패")


# ---------------------------------------------------------------------------
# 볼륨 Transfer (프로젝트 간 마이그레이션)
# ---------------------------------------------------------------------------


class CreateVolumeTransferRequest(BaseModel):
    name: str | None = None


class AcceptVolumeTransferRequest(BaseModel):
    auth_key: str = Field(..., min_length=1)


@router.get("/transfers")
async def list_volume_transfers(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """볼륨 이전(transfer) 목록 조회."""
    try:
        return await asyncio.to_thread(cinder.list_volume_transfers, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 이전 목록 조회 실패")


@router.post("/{volume_id}/transfer", status_code=201)
async def create_volume_transfer(
    volume_id: str,
    req: CreateVolumeTransferRequest | None = None,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 이전(transfer) 생성. VM에 연결된 경우 자동 detach 후 transfer를 생성한다."""
    try:
        vol = await asyncio.to_thread(cinder.get_volume, conn, volume_id)
    except Exception:
        raise HTTPException(status_code=404, detail="볼륨을 찾을 수 없습니다")

    for attachment in vol.attachments:
        server_id = attachment.get("server_id")
        if not server_id:
            continue
        try:
            await asyncio.to_thread(nova.detach_volume, conn, server_id, volume_id)
        except Exception:
            raise HTTPException(
                status_code=409,
                detail=f"볼륨 detach 실패 (인스턴스 {server_id}) — 수동으로 분리 후 재시도 해주세요",
            )

    if vol.attachments:
        for _ in range(30):
            await asyncio.sleep(2)
            try:
                refreshed = await asyncio.to_thread(cinder.get_volume, conn, volume_id)
                if refreshed.status == "available":
                    break
            except Exception:
                pass
        else:
            raise HTTPException(status_code=409, detail="볼륨 detach 대기 시간 초과")

    try:
        name = req.name if req else None
        result = await asyncio.to_thread(cinder.create_volume_transfer, conn, volume_id, name)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 이전 생성 실패")


@router.post("/transfer/{transfer_id}/accept", status_code=200)
async def accept_volume_transfer(
    transfer_id: str,
    req: AcceptVolumeTransferRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 이전 수락."""
    try:
        result = await asyncio.to_thread(cinder.accept_volume_transfer, conn, transfer_id, req.auth_key)
        await invalidate(f"afterglow:cinder:{conn._afterglow_project_id}:volumes")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 이전 수락 실패")


@router.delete("/transfer/{transfer_id}", status_code=204)
async def delete_volume_transfer(
    transfer_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 이전 취소."""
    try:
        await asyncio.to_thread(cinder.delete_volume_transfer, conn, transfer_id)
    except Exception:
        raise HTTPException(status_code=500, detail="볼륨 이전 취소 실패")
