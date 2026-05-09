from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.common.owner_check import assert_resource_owner
from app.api.deps import get_os_conn, get_token_info
from app.services import cinder
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


async def _assert_snapshot_owner(conn, snapshot_id: str, token_info: dict):
    try:
        s = await asyncio.to_thread(conn.block_storage.get_snapshot, snapshot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="스냅샷을 찾을 수 없습니다")
    assert_resource_owner(s, conn, token_info, not_found_detail="스냅샷을 찾을 수 없습니다")


async def _assert_volume_owner_local(conn, volume_id: str, token_info: dict):
    try:
        v = await asyncio.to_thread(conn.block_storage.get_volume, volume_id)
    except Exception:
        raise HTTPException(status_code=404, detail="볼륨을 찾을 수 없습니다")
    assert_resource_owner(v, conn, token_info, not_found_detail="볼륨을 찾을 수 없습니다")


class CreateSnapshotRequest(BaseModel):
    volume_id: str
    name: str
    description: str | None = None
    force: bool = False


@router.get("")
async def list_snapshots(
    volume_id: str | None = None,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
    refresh: bool = Query(False),
):
    pid = conn._afterglow_project_id
    is_admin = token_info.get("is_system_admin", False)
    caller_project_id = None if is_admin else pid
    vol_part = volume_id or "all"
    cache_key = f"afterglow:cinder:{pid}:snapshots:admin={int(is_admin)}:{vol_part}"
    try:
        return await cached_call(
            cache_key,
            ttl_fast(),
            lambda: cinder.list_snapshots(conn, volume_id, caller_project_id),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="스냅샷 목록 조회 실패")


@router.post("", status_code=201)
async def create_snapshot(
    req: CreateSnapshotRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    await _assert_volume_owner_local(conn, req.volume_id, token_info)
    try:
        result = await asyncio.to_thread(
            cinder.create_snapshot, conn, req.volume_id, req.name, req.description, req.force
        )
        await invalidate(f"afterglow:cinder:{pid}:snapshots")
        await rec(
            token_info,
            conn,
            resource_type="volume_snapshot",
            action="volume_snapshot.create",
            status="success",
            resource_name=req.name,
            extra={"volume_id": req.volume_id},
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="volume_snapshot",
            action="volume_snapshot.create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="스냅샷 생성 실패")


@router.get("/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    await _assert_snapshot_owner(conn, snapshot_id, token_info)
    try:
        return await asyncio.to_thread(cinder.get_snapshot, conn, snapshot_id)
    except Exception:
        raise HTTPException(status_code=404, detail="스냅샷을 찾을 수 없습니다")


@router.delete("/{snapshot_id}", status_code=204)
async def delete_snapshot(
    snapshot_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    await _assert_snapshot_owner(conn, snapshot_id, token_info)
    try:
        await asyncio.to_thread(cinder.delete_snapshot, conn, snapshot_id)
        await invalidate(f"afterglow:cinder:{pid}:snapshots")
        await rec(
            token_info,
            conn,
            resource_type="volume_snapshot",
            action="volume_snapshot.delete",
            status="success",
            resource_id=snapshot_id,
        )
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="volume_snapshot",
            action="volume_snapshot.delete",
            status="failed",
            resource_id=snapshot_id,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="스냅샷 삭제 실패")
