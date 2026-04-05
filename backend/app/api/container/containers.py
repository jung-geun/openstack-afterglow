import asyncio
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.models.containers import ZunContainerInfo, CreateZunContainerRequest
from app.services import zun

router = APIRouter()


@router.get("", response_model=list[ZunContainerInfo])
async def list_containers(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(zun.list_containers, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨테이너 목록 조회 실패: {e}")


@router.get("/{container_id}", response_model=ZunContainerInfo)
async def get_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(zun.get_container, conn, container_id)
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.post("", response_model=ZunContainerInfo, status_code=201)
async def create_container(
    req: CreateZunContainerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(
            zun.create_container, conn,
            req.name, req.image, req.command,
            req.cpu, req.memory, req.environment, req.auto_remove,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨테이너 생성 실패: {e}")


@router.delete("/{container_id}", status_code=204)
async def delete_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.delete_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨테이너 삭제 실패: {e}")


@router.post("/{container_id}/start", status_code=204)
async def start_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.start_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨테이너 시작 실패: {e}")


@router.post("/{container_id}/stop", status_code=204)
async def stop_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.stop_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨테이너 중지 실패: {e}")


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        logs = await asyncio.to_thread(zun.get_container_logs, conn, container_id)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그 조회 실패: {e}")
