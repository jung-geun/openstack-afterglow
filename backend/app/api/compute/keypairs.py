from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.deps import get_os_conn
from app.rate_limit import limiter
from app.services import nova
from app.services.cache import cached_call, invalidate, ttl_slow

router = APIRouter()


class CreateKeypairRequest(BaseModel):
    name: str
    public_key: str | None = None
    key_type: str = "ssh"


@router.get("")
async def list_keypairs(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    try:
        return await cached_call(
            f"afterglow:nova:{pid}:keypairs",
            ttl_slow(),
            lambda: nova.list_keypairs(conn),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("", status_code=201)
@limiter.limit("10/minute")
async def create_keypair(
    request: Request,
    req: CreateKeypairRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(nova.create_keypair, conn, req.name, req.public_key, req.key_type)
        await invalidate(f"afterglow:nova:{pid}:keypairs")
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="키페어 생성 실패")


@router.delete("/{keypair_name}", status_code=204)
@limiter.limit("10/minute")
async def delete_keypair(
    request: Request,
    keypair_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(nova.delete_keypair, conn, keypair_name)
        await invalidate(f"afterglow:nova:{pid}:keypairs")
    except Exception:
        raise HTTPException(status_code=500, detail="키페어 삭제 실패")
