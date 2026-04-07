import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn
from app.services import nova

router = APIRouter()


class CreateKeypairRequest(BaseModel):
    name: str
    public_key: str | None = None
    key_type: str = "ssh"


@router.get("")
async def list_keypairs(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(nova.list_keypairs, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("", status_code=201)
async def create_keypair(
    req: CreateKeypairRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(nova.create_keypair, conn, req.name, req.public_key, req.key_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail="키페어 생성 실패")


@router.delete("/{keypair_name}", status_code=204)
async def delete_keypair(
    keypair_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(nova.delete_keypair, conn, keypair_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail="키페어 삭제 실패")
