import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn
from app.services import cinder

router = APIRouter()


class CreateSnapshotRequest(BaseModel):
    volume_id: str
    name: str
    description: str | None = None
    force: bool = False


@router.get("")
async def list_snapshots(
    volume_id: str | None = None,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(cinder.list_snapshots, conn, volume_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스냅샷 목록 조회 실패: {e}")


@router.post("", status_code=201)
async def create_snapshot(
    req: CreateSnapshotRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(
            cinder.create_snapshot, conn, req.volume_id, req.name, req.description, req.force
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스냅샷 생성 실패: {e}")


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(cinder.get_snapshot, conn, snapshot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="스냅샷을 찾을 수 없습니다")


@router.delete("/{snapshot_id}", status_code=204)
async def delete_snapshot(snapshot_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(cinder.delete_snapshot, conn, snapshot_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스냅샷 삭제 실패: {e}")
