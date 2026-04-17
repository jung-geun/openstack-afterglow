import asyncio
import logging
import secrets

import openstack
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from app.api.deps import get_os_conn
from app.models.containers import (
    ContainerListResponse,
    CreateZunContainerRequest,
    ZunContainerInfo,
)
from app.rate_limit import limiter
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
        return ContainerListResponse(
            items=[],
            service_available=False,
            message="컨테이너 서비스에 연결할 수 없습니다",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 목록 조회 실패")


@router.get("/{container_id}", response_model=ZunContainerInfo)
async def get_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(zun.get_container, conn, container_id)
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.post("", response_model=ZunContainerInfo, status_code=201)
@limiter.limit("5/minute")
async def create_container(
    request: Request,
    req: CreateZunContainerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        ports = [p.model_dump(exclude_none=True) for p in req.ports] if req.ports else None
        return await asyncio.to_thread(
            zun.create_container,
            conn,
            req.name,
            req.image,
            req.command,
            req.cpu,
            req.memory,
            req.environment,
            req.auto_remove,
            ports,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 생성 실패")


@router.delete("/{container_id}", status_code=204)
async def delete_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.delete_container, conn, container_id)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 삭제 실패")


@router.post("/{container_id}/start", status_code=204)
async def start_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.start_container, conn, container_id)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 시작 실패")


@router.post("/{container_id}/stop", status_code=204)
async def stop_container(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(zun.stop_container, conn, container_id)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 중지 실패")


@router.get("/{container_id}/logs")
async def get_container_logs(container_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        logs = await asyncio.to_thread(zun.get_container_logs, conn, container_id)
        return {"logs": logs}
    except Exception:
        raise HTTPException(status_code=500, detail="로그 조회 실패")


class ExecRequest(BaseModel):
    command: str = "/bin/bash"


@router.post("/{container_id}/exec-ticket", status_code=201)
async def create_exec_ticket(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """WebSocket exec 연결에 사용할 일회용 티켓 발급 (30초 유효)."""
    import json

    from app.services.cache import _get_redis

    ticket = secrets.token_urlsafe(32)
    payload = json.dumps(
        {
            "container_id": container_id,
            "user_id": conn._afterglow_user_id,
            "project_id": conn._afterglow_project_id,
            "token": conn._afterglow_token,
        }
    )
    r = await _get_redis()
    await r.setex(f"afterglow:ws-ticket:{ticket}", 30, payload)
    return {"ticket": ticket}


@router.websocket("/{container_id}/exec")
async def container_exec_ws(
    container_id: str,
    websocket: WebSocket,
    ticket: str = Query(...),
):
    """컨테이너 exec 인터랙티브 WebSocket 프록시.
    Zun execute API를 통해 명령을 실행하고 결과를 반환하는 간단한 셸 에뮬레이터.
    인증은 일회용 티켓으로 처리 (POST /{id}/exec-ticket 으로 발급).
    """
    await websocket.accept()
    conn = None
    try:
        import json

        from app.services import keystone
        from app.services.cache import _get_redis

        r = await _get_redis()
        ticket_key = f"afterglow:ws-ticket:{ticket}"
        payload_bytes = await r.get(ticket_key)
        if not payload_bytes:
            await websocket.close(code=4001)
            return
        await r.delete(ticket_key)  # 일회용: 즉시 삭제

        payload = json.loads(payload_bytes)
        if payload.get("container_id") != container_id:
            await websocket.close(code=4001)
            return

        scoped_token = payload["token"]
        pid = payload["project_id"]
        conn = await asyncio.to_thread(keystone.get_openstack_connection, scoped_token, pid)
        conn._afterglow_token = scoped_token
        conn._afterglow_project_id = pid

        endpoint = zun._get_zun_endpoint(conn)
        await websocket.send_text(
            "\r\n\x1b[32mZun 컨테이너 콘솔에 연결됨\x1b[0m\r\n\x1b[33m명령어를 입력하세요 (exit 로 종료)\x1b[0m\r\n$ "
        )

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
                    lambda _body=body: conn.session.post(f"{endpoint}/v1/containers/{container_id}/execute", json=_body)
                )
                result = resp.json() if hasattr(resp, "json") else {}
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
