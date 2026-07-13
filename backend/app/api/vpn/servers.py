"""VPN 서버 관리 API — 사용자 JWT 인증 + project_id 소유권 검증."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_token_info
from app.config import get_settings
from app.database import is_db_available
from app.models.vpn import VpnServerCreateRequest, VpnServerInfo
from app.services import vpn_agent_auth, vpn_db
from app.services.vpn_provisioner import delete_vpn_server, provision_vpn_server

router = APIRouter()
_logger = logging.getLogger(__name__)


def _require_db() -> None:
    if not is_db_available():
        raise HTTPException(status_code=503, detail="DB를 사용할 수 없습니다")


async def _merge_status(server: dict) -> VpnServerInfo:
    """DB 레코드 + Redis 최신 상태(에이전트 마지막 보고)를 병합해 VpnServerInfo를 만든다."""
    info = VpnServerInfo(**{k: v for k, v in server.items() if k in VpnServerInfo.model_fields})
    status_result = await vpn_agent_auth.get_status_result(server["id"])
    if status_result:
        info.last_status_reported_at = status_result.get("_stored_at")
        info.peer_count = len(status_result.get("peers", []))
    return info


@router.post("", status_code=201, response_model=VpnServerInfo)
@router.post("/", status_code=201, response_model=VpnServerInfo, include_in_schema=False)
async def create_vpn_server(
    body: VpnServerCreateRequest,
    token_info: dict = Depends(get_token_info),
):
    """VPN 서버 프로비저닝 요청 — CREATING 상태로 즉시 응답, 백그라운드에서 부팅."""
    _require_db()
    settings = get_settings()
    if not settings.vpn_provider_network_id or not settings.vpn_image_id:
        raise HTTPException(
            status_code=503,
            detail="VPN 기능이 설정되지 않았습니다 (afterglow.conf [vpn] provider_network_id/image_id 필요)",
        )

    project_id = token_info["project_id"]
    server_id = str(uuid.uuid4())

    await vpn_db.create_server_record(
        project_id,
        server_id,
        {
            "name": body.name,
            "status": "CREATING",
            "listen_port": settings.vpn_default_listen_port,
            "tunnel_cidr": settings.vpn_default_tunnel_cidr,
            "created_by_user_id": token_info.get("user_id"),
            "created_by_username": token_info.get("username"),
        },
    )

    asyncio.create_task(
        provision_vpn_server(project_id, server_id, token_info.get("user_id", ""), token_info.get("username", ""))
    )

    server = await vpn_db.get_server(project_id, server_id)
    return await _merge_status(server)


@router.get("", response_model=list[VpnServerInfo])
@router.get("/", response_model=list[VpnServerInfo], include_in_schema=False)
async def list_vpn_servers(token_info: dict = Depends(get_token_info)):
    _require_db()
    project_id = token_info["project_id"]
    servers = await vpn_db.list_servers(project_id)
    return [await _merge_status(s) for s in servers]


@router.get("/{server_id}", response_model=VpnServerInfo)
async def get_vpn_server(server_id: str, token_info: dict = Depends(get_token_info)):
    _require_db()
    project_id = token_info["project_id"]
    server = await vpn_db.get_server(project_id, server_id)
    if not server:
        # 정보 노출 방지 — 존재하지 않음/타 프로젝트 소유 모두 동일 404
        raise HTTPException(status_code=404, detail="VPN 서버를 찾을 수 없습니다")
    return await _merge_status(server)


@router.delete("/{server_id}", status_code=202)
async def delete_vpn_server_endpoint(server_id: str, token_info: dict = Depends(get_token_info)):
    _require_db()
    project_id = token_info["project_id"]
    server = await vpn_db.get_server(project_id, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="VPN 서버를 찾을 수 없습니다")

    asyncio.create_task(delete_vpn_server(project_id, server_id, token_info.get("user_id", "")))
    return {"ok": True, "status": "DELETING"}
