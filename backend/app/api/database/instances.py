import asyncio

import openstack
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_os_conn

router = APIRouter()


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
