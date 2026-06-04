from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.deps import cache_bypass, get_os_conn, get_token_info
from app.rate_limit import limiter
from app.services import nova
from app.services.cache import cached_call, invalidate, invalidation, keys, ttl_slow

router = APIRouter()


class CreateKeypairRequest(BaseModel):
    name: str
    public_key: str | None = None
    key_type: str = "ssh"


@router.get("")
async def list_keypairs(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    bypass: bool = Depends(cache_bypass),
):
    pid = conn._afterglow_project_id
    key = keys.project_key("nova", pid, "keypairs")
    try:
        return await cached_call(key, ttl_slow(), lambda: nova.list_keypairs(conn), refresh=bypass)
    except Exception:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("", status_code=201)
@limiter.limit("10/minute")
async def create_keypair(
    request: Request,
    req: CreateKeypairRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        result = await asyncio.to_thread(nova.create_keypair, conn, req.name, req.public_key, req.key_type)
        await invalidate(f"{keys.project_key('nova', pid, 'keypairs')}*")
        await invalidation.invalidate_mutation_count("nova", pid)
        await rec(
            token_info, conn, resource_type="keypair", action="keypair.create", status="success", resource_name=req.name
        )
        return result
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="keypair",
            action="keypair.create",
            status="failed",
            resource_name=req.name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="키페어 생성 실패")


@router.delete("/{keypair_name}", status_code=204)
@limiter.limit("10/minute")
async def delete_keypair(
    request: Request,
    keypair_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    pid = conn._afterglow_project_id
    try:
        await asyncio.to_thread(nova.delete_keypair, conn, keypair_name)
        await invalidate(f"{keys.project_key('nova', pid, 'keypairs')}*")
        await invalidation.invalidate_mutation_count("nova", pid)
        await rec(
            token_info,
            conn,
            resource_type="keypair",
            action="keypair.delete",
            status="success",
            resource_id=keypair_name,
            resource_name=keypair_name,
        )
    except Exception as e:
        await rec(
            token_info,
            conn,
            resource_type="keypair",
            action="keypair.delete",
            status="failed",
            resource_id=keypair_name,
            resource_name=keypair_name,
            error_message=str(e)[:500],
        )
        raise HTTPException(status_code=500, detail="키페어 삭제 실패")
