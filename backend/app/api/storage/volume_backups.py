import asyncio

import openstack
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn
from app.services import cinder
from app.services.cache import cached_call, ttl_fast

router = APIRouter()


class CreateBackupRequest(BaseModel):
    volume_id: str
    name: str
    description: str | None = None
    incremental: bool = False


class RestoreBackupRequest(BaseModel):
    volume_id: str | None = None


@router.get("")
async def list_backups(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"afterglow:cinder:{pid}:backups",
            ttl_fast(),
            lambda: cinder.list_backups(conn),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="백업 목록 조회 실패")


@router.post("", status_code=201)
async def create_backup(
    req: CreateBackupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(
            cinder.create_backup, conn, req.volume_id, req.name, req.description, req.incremental
        )
    except Exception:
        raise HTTPException(status_code=500, detail="백업 생성 실패")


@router.get("/{backup_id}")
async def get_backup(backup_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(cinder.get_backup, conn, backup_id)
    except Exception:
        raise HTTPException(status_code=404, detail="백업을 찾을 수 없습니다")


@router.delete("/{backup_id}", status_code=204)
async def delete_backup(backup_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(cinder.delete_backup, conn, backup_id)
    except Exception:
        raise HTTPException(status_code=500, detail="백업 삭제 실패")


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    req: RestoreBackupRequest = RestoreBackupRequest(),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(cinder.restore_backup, conn, backup_id, req.volume_id)
    except Exception:
        raise HTTPException(status_code=500, detail="백업 복원 실패")
