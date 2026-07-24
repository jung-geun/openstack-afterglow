"""VPN 에이전트 베어러 토큰 발급/검증 + Redis 상태 캐시.

`app/services/instance_health.py`와 동일 패턴이지만 Redis 키 프리픽스를 구분하고,
토큰 payload에 instance_id 대신 {server_id, project_id}를 담는다.
"""

import json
import logging
import secrets
from datetime import UTC, datetime

from app.models.waygate import WaygateAgentStatusReport

_logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "afterglow:waygate:token:"
_SERVER_PREFIX = "afterglow:waygate:server:"
_STATUS_PREFIX = "afterglow:waygate:status:"
# 절대 만료 7일 — instance_health와 동일 관례. VM userdata 노출 시에도 7일 후 토큰 무효화.
_TOKEN_TTL = 86400 * 7
_STATUS_TTL = 300  # 5분 (reconcile 주기 15초 대비 충분한 여유)


async def _redis():
    from app.services.cache import _get_client

    return _get_client()


# ---------------------------------------------------------------------------
# 토큰 lifecycle
# ---------------------------------------------------------------------------


async def issue_report_token(server_id: str, project_id: str) -> str:
    """VPN reconcile 베어러 토큰 발급. 이미 존재하면 기존 토큰을 폐기 후 재발급."""
    await revoke_report_token_by_server(server_id)

    token = secrets.token_urlsafe(32)
    r = await _redis()
    payload = json.dumps({"server_id": server_id, "project_id": project_id})
    await r.setex(f"{_TOKEN_PREFIX}{token}", _TOKEN_TTL, payload)
    await r.setex(f"{_SERVER_PREFIX}{server_id}", _TOKEN_TTL, token)
    return token


async def verify_report_token(token: str) -> dict | None:
    """토큰 검증. 성공 시 {server_id, project_id} 반환. fail-closed(예외 시 None)."""
    try:
        r = await _redis()
        raw = await r.get(f"{_TOKEN_PREFIX}{token}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        _logger.warning("vpn_agent_auth: 토큰 검증 실패", exc_info=True)
        return None


async def revoke_report_token_by_server(server_id: str) -> None:
    """VPN 서버 삭제 시 역인덱스로 토큰 lookup 후 두 키 모두 삭제."""
    try:
        r = await _redis()
        token = await r.get(f"{_SERVER_PREFIX}{server_id}")
        if token:
            if isinstance(token, bytes):
                token = token.decode()
            await r.delete(f"{_TOKEN_PREFIX}{token}")
        await r.delete(f"{_SERVER_PREFIX}{server_id}")
    except Exception:
        _logger.warning("vpn_agent_auth: 토큰 폐기 실패 (server=%s)", server_id, exc_info=True)


# ---------------------------------------------------------------------------
# 상태 캐시 (wg show 결과)
# ---------------------------------------------------------------------------


async def store_status_result(server_id: str, report: WaygateAgentStatusReport) -> None:
    """에이전트가 보고한 wg show 상태를 Redis에 저장 (TTL 5분)."""
    try:
        r = await _redis()
        payload = report.model_dump()
        payload["_stored_at"] = datetime.now(UTC).isoformat()
        await r.setex(f"{_STATUS_PREFIX}{server_id}", _STATUS_TTL, json.dumps(payload))
    except Exception:
        _logger.warning("vpn_agent_auth: Redis 상태 저장 실패 (server=%s)", server_id, exc_info=True)


async def get_status_result(server_id: str) -> dict | None:
    """Redis에서 최신 wg show 상태를 조회한다. 없거나 만료 시 None."""
    try:
        r = await _redis()
        raw = await r.get(f"{_STATUS_PREFIX}{server_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        _logger.warning("vpn_agent_auth: Redis 상태 조회 실패 (server=%s)", server_id, exc_info=True)
        return None
