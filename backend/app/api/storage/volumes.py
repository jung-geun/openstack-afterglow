import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
import openstack

from app.api.deps import get_os_conn
from app.models.storage import VolumeInfo, CreateVolumeRequest
from app.rate_limit import limiter
from app.services import cinder
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("", response_model=list[VolumeInfo])
async def list_volumes(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:cinder:{pid}:volumes", ttl_fast(),
            lambda: [v.model_dump() for v in cinder.list_volumes(conn)],
            refresh=refresh,
        )
    except Exception as e:
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
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(cinder.create_empty_volume, conn, req.name, req.size_gb, req.availability_zone)
        await invalidate(f"union:cinder:{pid}:volumes")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="볼륨 생성 실패")


@router.delete("/{volume_id}", status_code=204)
async def delete_volume(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(cinder.delete_volume, conn, volume_id)
        await invalidate(f"union:cinder:{pid}:volumes")
    except Exception as e:
        raise HTTPException(status_code=500, detail="볼륨 삭제 실패")


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
    """볼륨 이전(transfer) 생성. 반환된 auth_key를 수락 측에 전달해야 함."""
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
        await invalidate(f"union:cinder:{conn._union_project_id}:volumes")
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
