"""관리자 서비스 상태 모니터링 엔드포인트."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn, require_admin

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/services", dependencies=[Depends(require_admin)])
async def list_services(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """Nova, Cinder, Neutron 서비스 에이전트 상태 조회."""
    def _collect():
        result: dict = {
            "compute": [],
            "block_storage": [],
            "network": [],
        }

        # Nova compute services
        try:
            for svc in conn.compute.services():
                result["compute"].append({
                    "id": getattr(svc, 'id', ''),
                    "binary": svc.binary or '',
                    "host": svc.host or '',
                    "status": svc.status or '',
                    "state": svc.state or '',
                    "zone": getattr(svc, 'zone', ''),
                    "updated_at": str(svc.updated_at) if getattr(svc, 'updated_at', None) else None,
                    "disabled_reason": getattr(svc, 'disabled_reason', None),
                })
        except Exception:
            _logger.warning("Nova 서비스 조회 실패", exc_info=True)

        # Cinder volume services
        try:
            for svc in conn.block_storage.services():
                result["block_storage"].append({
                    "id": getattr(svc, 'id', ''),
                    "binary": svc.binary or '',
                    "host": svc.host or '',
                    "status": svc.status or '',
                    "state": svc.state or '',
                    "zone": getattr(svc, 'zone', ''),
                    "updated_at": str(svc.updated_at) if getattr(svc, 'updated_at', None) else None,
                    "disabled_reason": getattr(svc, 'disabled_reason', None),
                })
        except Exception:
            _logger.warning("Cinder 서비스 조회 실패", exc_info=True)

        # Neutron agents
        try:
            for agent in conn.network.agents():
                result["network"].append({
                    "id": agent.id,
                    "binary": agent.binary or '',
                    "host": agent.host or '',
                    "agent_type": getattr(agent, 'agent_type', ''),
                    "alive": agent.is_alive,
                    "admin_state_up": getattr(agent, 'admin_state_up', True),
                    "updated_at": str(agent.updated_at) if getattr(agent, 'updated_at', None) else None,
                })
        except Exception:
            _logger.warning("Neutron 에이전트 조회 실패", exc_info=True)

        return result

    try:
        return await asyncio.to_thread(_collect)
    except Exception:
        raise HTTPException(status_code=500, detail="서비스 상태 조회 실패")