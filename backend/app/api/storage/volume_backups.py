import asyncio

import openstack
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn
from app.services import auto_backup, cinder
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
    pid = conn._afterglow_project_id
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


# ────────── 자동 백업 설정 엔드포인트 ──────────


class AutoBackupRequest(BaseModel):
    max_daily: int = 2
    max_weekly: int = 2
    max_monthly: int = 1


@router.post("/auto-backup/configs")
async def list_auto_backup_configs(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 프로젝트의 모든 자동 백업 설정 목록."""
    project_id = conn._afterglow_project_id
    try:
        return await auto_backup.list_auto_backup_configs(project_id)
    except Exception:
        raise HTTPException(status_code=500, detail="자동 백업 설정 목록 조회 실패")


@router.get("/auto-backup/{volume_id}")
async def get_auto_backup_config(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨의 자동 백업 설정 조회."""
    project_id = conn._afterglow_project_id
    config = await auto_backup.get_auto_backup_config(project_id, volume_id)
    if config is None:
        raise HTTPException(status_code=404, detail="자동 백업 설정이 없습니다")
    return config


@router.post("/auto-backup/{volume_id}", status_code=201)
async def enable_auto_backup(
    volume_id: str,
    req: AutoBackupRequest = AutoBackupRequest(),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 자동 백업 활성화."""
    project_id = conn._afterglow_project_id
    try:
        return await auto_backup.enable_auto_backup(
            project_id,
            volume_id,
            max_daily=req.max_daily,
            max_weekly=req.max_weekly,
            max_monthly=req.max_monthly,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="자동 백업 활성화 실패")


@router.delete("/auto-backup/{volume_id}", status_code=204)
async def disable_auto_backup(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 자동 백업 비활성화."""
    project_id = conn._afterglow_project_id
    try:
        await auto_backup.disable_auto_backup(project_id, volume_id)
    except Exception:
        raise HTTPException(status_code=500, detail="자동 백업 비활성화 실패")
