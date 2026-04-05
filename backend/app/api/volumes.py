import asyncio
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.models.storage import VolumeInfo, CreateVolumeRequest
from app.services import cinder
from app.services.cache import cached_call, invalidate

router = APIRouter()


@router.get("", response_model=list[VolumeInfo])
async def list_volumes(conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:cinder:{pid}:volumes", 15,
            lambda: [v.model_dump() for v in cinder.list_volumes(conn)]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"볼륨 목록 조회 실패: {e}")


@router.get("/{volume_id}", response_model=VolumeInfo)
async def get_volume(volume_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(cinder.get_volume, conn, volume_id)
    except Exception:
        raise HTTPException(status_code=404, detail="볼륨을 찾을 수 없습니다")


@router.post("", response_model=VolumeInfo, status_code=201)
async def create_volume(
    req: CreateVolumeRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(cinder.create_empty_volume, conn, req.name, req.size_gb, req.availability_zone)
        await invalidate(f"union:cinder:{pid}:volumes")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"볼륨 생성 실패: {e}")


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
        raise HTTPException(status_code=500, detail=f"볼륨 삭제 실패: {e}")
