import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn
from app.models.storage import ShareSnapshotInfo, CreateShareSnapshotRequest
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("", response_model=list[ShareSnapshotInfo])
async def list_share_snapshots(
    share_id: str | None = Query(None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
):
    pid = conn._union_project_id
    cache_key = f"union:manila:{pid}:share_snapshots" if not share_id else f"union:manila:{pid}:share_snapshots:{share_id}"
    try:
        return await cached_call(
            cache_key, ttl_fast(),
            lambda: [_normalize_snapshot(s) for s in manila.list_share_snapshots(conn, share_id)],
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="스냅샷 목록 조회 실패")


@router.post("", response_model=ShareSnapshotInfo, status_code=201)
async def create_share_snapshot(
    req: CreateShareSnapshotRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(
            manila.create_share_snapshot, conn, req.share_id, req.name, req.description
        )
        await invalidate(f"union:manila:{pid}:share_snapshots")
        return _normalize_snapshot(result)
    except Exception:
        raise HTTPException(status_code=500, detail="스냅샷 생성 실패")


@router.delete("/{snapshot_id}", status_code=204)
async def delete_share_snapshot(
    snapshot_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(manila.delete_share_snapshot, conn, snapshot_id)
        await invalidate(f"union:manila:{pid}:share_snapshots")
    except Exception:
        raise HTTPException(status_code=500, detail="스냅샷 삭제 실패")


def _normalize_snapshot(s: dict) -> dict:
    return {
        "id": s.get("id", ""),
        "name": s.get("name", ""),
        "status": s.get("status", ""),
        "share_id": s.get("share_id", ""),
        "size": s.get("size", 0),
        "description": s.get("description"),
        "created_at": str(s.get("created_at")) if s.get("created_at") else None,
    }
