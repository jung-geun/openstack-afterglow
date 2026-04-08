import asyncio
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn
from app.models.containers import ZunContainerInfo, CreateZunContainerRequest, ContainerListResponse, PortMapping
from app.services import zun
from app.services.zun import ZunServiceUnavailable

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ContainerListResponse)
async def list_containers(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        items = await asyncio.to_thread(zun.list_containers, conn)
        return ContainerListResponse(items=items)
    except ZunServiceUnavailable:
        return ContainerListResponse(items=[], service_available=False, message="컨테이너 서비스에 연결할 수 없습니다")
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 목록 조회 실패")


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
        ports = [p.model_dump(exclude_none=True) for p in req.ports] if req.ports else None
        return await asyncio.to_thread(
            zun.create_container, conn,
            req.name, req.image, req.command,
            req.cpu, req.memory, req.environment, req.auto_remove, ports,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 생성 실패")


@router.delete("/{container_id}", status_code=204)
async def delete_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.delete_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 삭제 실패")


@router.post("/{container_id}/start", status_code=204)
async def start_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.start_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 시작 실패")


@router.post("/{container_id}/stop", status_code=204)
async def stop_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.stop_container, conn, container_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 중지 실패")


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        logs = await asyncio.to_thread(zun.get_container_logs, conn, container_id)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail="로그 조회 실패")


class ExecRequest(BaseModel):
    command: str = "/bin/bash"


@router.websocket("/{container_id}/exec")
async def container_exec_ws(
    container_id: str,
    websocket: WebSocket,
    token: str = Query(...),
    project_id: str = Query(default=""),
):
    """컨테이너 exec 인터랙티브 WebSocket 프록시.
    Zun execute API를 통해 명령을 실행하고 결과를 반환하는 간단한 셸 에뮬레이터.
    """
    await websocket.accept()
    conn = None
    try:
        from app.api.deps import _cached_validate, _check_session_timeout
        from app.services import keystone

        token_info = await _cached_validate(token, project_id)
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        await _check_session_timeout(token_hash, project_id)
        scoped_token = token_info["token"]
        pid = token_info["project_id"]
        conn = await asyncio.to_thread(keystone.get_openstack_connection, scoped_token, pid)
        conn._union_token = scoped_token
        conn._union_project_id = pid

        endpoint = zun._get_zun_endpoint(conn)
        await websocket.send_text("\r\n\x1b[32mZun 컨테이너 콘솔에 연결됨\x1b[0m\r\n\x1b[33m명령어를 입력하세요 (exit 로 종료)\x1b[0m\r\n$ ")

        while True:
            data = await websocket.receive_text()
            cmd = data.strip()
            if cmd in ("exit", "quit", "logout"):
                await websocket.send_text("\r\n연결 종료\r\n")
                break
            if not cmd:
                await websocket.send_text("$ ")
                continue
            try:
                body = {"command": ["/bin/sh", "-c", cmd]}
                resp = await asyncio.to_thread(
                    lambda: conn.session.post(f"{endpoint}/v1/containers/{container_id}/execute", json=body)
                )
                result = resp.json() if hasattr(resp, 'json') else {}
                output = result.get("output", "")
                exit_code = result.get("exit_code", 0)
                if output:
                    await websocket.send_text(output.replace("\n", "\r\n"))
                if exit_code != 0:
                    await websocket.send_text(f"\r\n\x1b[31m[exit {exit_code}]\x1b[0m")
                await websocket.send_text("\r\n$ ")
            except Exception as e:
                logger.warning("Container exec command error: %s", e)
                await websocket.send_text("\r\n\x1b[31m명령 실행에 실패했습니다\x1b[0m\r\n$ ")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Container exec WS error: %s", e)
        try:
            await websocket.send_text("\r\n\x1b[31m연결 오류가 발생했습니다\x1b[0m\r\n")
            await websocket.close()
        except Exception:
            pass
    finally:
        if conn:
            try:
                await asyncio.to_thread(conn.close)
            except Exception:
                pass
