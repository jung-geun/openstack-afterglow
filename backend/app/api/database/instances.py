from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_os_conn
from app.models.database import (
    CreateBackupRequest,
    CreateDatabaseRequest,
    CreateDbInstanceRequest,
    CreateUserRequest,
    RestoreFromBackupRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# 플레이버 / 데이터스토어 (인스턴스 생성에 필요한 메타데이터)
# ---------------------------------------------------------------------------


@router.get("/flavors")
async def list_db_flavors(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """DB 플레이버 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_flavors, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="DB 플레이버 목록 조회 실패")


@router.get("/datastores")
async def list_datastores(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """데이터스토어(MySQL, MariaDB, PostgreSQL 등) 및 버전 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_datastores, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="데이터스토어 목록 조회 실패")


# ---------------------------------------------------------------------------
# 백업 (인스턴스 ID 없는 전역 목록 / 삭제 / 복원)
# ---------------------------------------------------------------------------


@router.delete("/backups/{backup_id}", status_code=204)
async def delete_backup(
    backup_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """백업 삭제."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.delete_backup, conn, backup_id)
    except Exception:
        raise HTTPException(status_code=500, detail="백업 삭제 실패")


@router.post("/restore", status_code=201)
async def restore_from_backup(
    req: RestoreFromBackupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """백업에서 새 인스턴스 복원."""
    from app.services import trove

    try:
        return await asyncio.to_thread(
            trove.create_instance,
            conn,
            req.name,
            req.flavor_id,
            req.volume_size,
            "",
            "",
            None,
            None,
            req.backup_id,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="백업 복원 실패")


# ---------------------------------------------------------------------------
# 인스턴스 목록 / 생성
# ---------------------------------------------------------------------------


@router.get("")
async def list_database_instances(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 프로젝트의 Trove DB 인스턴스 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_instances, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="DB 인스턴스 목록 조회 실패")


@router.post("", status_code=201)
async def create_database_instance(
    req: CreateDbInstanceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """DB 인스턴스 생성."""
    import logging

    _logger = logging.getLogger(__name__)

    from app.services import trove

    try:
        return await asyncio.to_thread(
            trove.create_instance,
            conn,
            req.name,
            req.flavor_id,
            req.volume_size,
            req.datastore_type,
            req.datastore_version,
            req.databases or None,
            None,
            req.restore_backup_id,
        )
    except Exception as e:
        _logger.exception(
            "DB 인스턴스 생성 실패: name=%s, datastore=%s/%s", req.name, req.datastore_type, req.datastore_version
        )
        raise HTTPException(status_code=500, detail=f"DB 인스턴스 생성 실패: {str(e)}")


# ---------------------------------------------------------------------------
# 개별 인스턴스 — 상세 / 삭제 / 액션
# ---------------------------------------------------------------------------


@router.get("/{instance_id}")
async def get_database_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """DB 인스턴스 상세."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.get_instance, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="DB 인스턴스를 찾을 수 없습니다")


@router.delete("/{instance_id}", status_code=204)
async def delete_database_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """DB 인스턴스 삭제."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.delete_instance, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="DB 인스턴스 삭제 실패")


@router.post("/{instance_id}/restart", status_code=204)
async def restart_database_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """DB 인스턴스 재시작."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.restart_instance, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="DB 인스턴스 재시작 실패")


@router.post("/{instance_id}/root")
async def enable_root_user(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """root 유저 활성화. {name, password} 반환."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.enable_root, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="root 유저 활성화 실패")


# ---------------------------------------------------------------------------
# 데이터베이스 서브리소스
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/databases")
async def list_instance_databases(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 데이터베이스 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_databases, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="데이터베이스 목록 조회 실패")


@router.post("/{instance_id}/databases", status_code=201)
async def create_instance_database(
    instance_id: str,
    req: CreateDatabaseRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 데이터베이스 생성."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.create_database, conn, instance_id, req.name, req.character_set, req.collate)
        return {"name": req.name}
    except Exception:
        raise HTTPException(status_code=500, detail="데이터베이스 생성 실패")


@router.delete("/{instance_id}/databases/{db_name}", status_code=204)
async def delete_instance_database(
    instance_id: str,
    db_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 데이터베이스 삭제."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.delete_database, conn, instance_id, db_name)
    except Exception:
        raise HTTPException(status_code=500, detail="데이터베이스 삭제 실패")


# ---------------------------------------------------------------------------
# 유저 서브리소스
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/users")
async def list_instance_users(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 유저 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_users, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="유저 목록 조회 실패")


@router.post("/{instance_id}/users", status_code=201)
async def create_instance_user(
    instance_id: str,
    req: CreateUserRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 유저 생성."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.create_user, conn, instance_id, req.name, req.password, req.databases or None)
        return {"name": req.name}
    except Exception:
        raise HTTPException(status_code=500, detail="유저 생성 실패")


@router.delete("/{instance_id}/users/{username}", status_code=204)
async def delete_instance_user(
    instance_id: str,
    username: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 내 유저 삭제."""
    from app.services import trove

    try:
        await asyncio.to_thread(trove.delete_user, conn, instance_id, username)
    except Exception:
        raise HTTPException(status_code=500, detail="유저 삭제 실패")


# ---------------------------------------------------------------------------
# 백업 서브리소스
# ---------------------------------------------------------------------------


@router.get("/{instance_id}/backups")
async def list_instance_backups(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 백업 목록."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.list_backups, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=500, detail="백업 목록 조회 실패")


@router.post("/{instance_id}/backups", status_code=201)
async def create_instance_backup(
    instance_id: str,
    req: CreateBackupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 백업 생성."""
    from app.services import trove

    try:
        return await asyncio.to_thread(trove.create_backup, conn, instance_id, req.name, req.description)
    except Exception:
        raise HTTPException(status_code=500, detail="백업 생성 실패")
