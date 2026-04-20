import asyncio

import openstack
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_os_conn

router = APIRouter()


@router.get("")
async def list_object_storage_containers(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 계정의 Swift 오브젝트 스토리지 컨테이너 목록."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.list_containers, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 컨테이너 목록 조회 실패")


@router.get("/account")
async def get_object_storage_account(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 계정의 Swift 오브젝트 스토리지 사용량 메타데이터."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_account_metadata, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 계정 정보 조회 실패")
