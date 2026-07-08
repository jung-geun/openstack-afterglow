"""
GitLab OIDC 인증 서비스.

흐름:
1. get_authorize_url() → GitLab OAuth2 authorize URL + state 생성 (Redis에 저장)
2. exchange_code(code, state) →
   - state 검증
   - GitLab 토큰 엔드포인트에서 access_token 획득
   - Keystone OS-FEDERATION으로 unscoped 토큰 획득
   - 프로젝트 목록 조회 후 첫 번째 프로젝트로 scope
   - TokenResponse 호환 dict 반환
"""

import asyncio
import logging
import secrets
import urllib.parse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


_STATE_TTL = 600  # 10분
_FALLBACK_MAX_SIZE = 500  # 인메모리 폴백 최대 항목 수 (메모리 누수 방지)

# Redis 장애 시 인메모리 state 폴백 (단일 프로세스용, 재시작 시 소실)
# {state: (expiry_timestamp, nonce)} — 최대 _FALLBACK_MAX_SIZE 항목 유지
_fallback_states: dict[str, tuple[float, str]] = {}


async def _get_redis():
    from app.services.cache import _get_redis as _cache_redis

    return await _cache_redis()


async def get_authorize_url() -> str:
    """GitLab OAuth2 authorize URL을 생성하고 state(값=nonce)를 Redis에 저장."""
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    try:
        r = await _get_redis()
        # state 키의 값으로 nonce를 저장 — 콜백에서 id_token nonce 클레임 검증에 사용
        await r.setex(f"afterglow:gitlab_state:{state}", _STATE_TTL, nonce)
    except Exception:
        logger.warning("Redis 장애로 OIDC state를 인메모리에 임시 저장합니다")
        import time as _time

        now = _time.time()
        # 크기 초과 시 만료된 항목 정리 (메모리 누수 방지)
        if len(_fallback_states) >= _FALLBACK_MAX_SIZE:
            expired = [k for k, (exp, _n) in _fallback_states.items() if exp <= now]
            for k in expired:
                del _fallback_states[k]
            # 여전히 초과하면 가장 오래된 항목 제거
            if len(_fallback_states) >= _FALLBACK_MAX_SIZE:
                oldest = min(_fallback_states, key=lambda k: _fallback_states[k][0])
                del _fallback_states[oldest]
        _fallback_states[state] = (now + _STATE_TTL, nonce)

    params = {
        "client_id": settings.gitlab_oidc_client_id,
        "redirect_uri": settings.gitlab_oidc_redirect_uri,
        "response_type": "code",
        "scope": settings.gitlab_oidc_scopes,
        "state": state,
        "nonce": nonce,
    }
    query = urllib.parse.urlencode(params)
    return f"{settings.gitlab_oidc_gitlab_url}/oauth/authorize?{query}"


async def _validate_state(state: str) -> str:
    """Redis에서 state 검증 후 삭제. nonce 반환. Redis 장애 시 인메모리 폴백 확인."""
    import time as _time

    # Redis 시도
    try:
        r = await _get_redis()
        key = f"afterglow:gitlab_state:{state}"
        val = await r.get(key)
        if val is not None:
            await r.delete(key)
            return val.decode() if isinstance(val, bytes) else val
    except Exception:
        logger.warning("Redis 장애로 state 검증을 인메모리 폴백으로 시도합니다")

    # 인메모리 폴백 확인
    entry = _fallback_states.pop(state, None)
    if entry is not None:
        expiry, nonce = entry
        if _time.time() < expiry:
            return nonce

    raise ValueError("유효하지 않거나 만료된 state입니다")


async def _exchange_gitlab_code(code: str) -> dict:
    """GitLab 토큰 엔드포인트에서 authorization code를 토큰으로 교환."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30, verify=settings.ssl_verify) as client:
        resp = await client.post(
            f"{settings.gitlab_oidc_gitlab_url}/oauth/token",
            json={
                "client_id": settings.gitlab_oidc_client_id,
                "client_secret": settings.gitlab_oidc_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.gitlab_oidc_redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            logger.debug("GitLab 토큰 응답에 access_token 없음 (keys: %s)", list(data.keys()))
            raise ValueError("GitLab 토큰 응답에 access_token이 없습니다")
        # Keystone OS-FEDERATION OpenID Connect는 id_token(JWT)을 기대함
        id_token = data.get("id_token", access_token)
        return {"access_token": access_token, "id_token": id_token}


async def _federated_auth(token: str) -> dict:
    """
    GitLab id_token으로 Keystone OS-FEDERATION 인증.
    unscoped Keystone 토큰과 사용자 정보를 반환.
    """
    settings = get_settings()
    url = (
        f"{settings.os_auth_url}/OS-FEDERATION"
        f"/identity_providers/{settings.gitlab_oidc_idp_id}"
        f"/protocols/{settings.gitlab_oidc_protocol_id}/auth"
    )
    async with httpx.AsyncClient(timeout=30, verify=settings.ssl_verify) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        unscoped_token = resp.headers.get("X-Subject-Token", "")
        if not unscoped_token:
            raise ValueError("Keystone federation 응답에 X-Subject-Token 없음")
        body = resp.json()
        user = body.get("token", {}).get("user", {})
        return {"token": unscoped_token, "user": user}


async def _list_projects_for_token(unscoped_token: str) -> list[dict]:
    """unscoped 토큰으로 접근 가능한 프로젝트 목록 조회."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30, verify=settings.ssl_verify) as client:
        resp = await client.get(
            f"{settings.os_auth_url}/auth/projects",
            headers={"X-Auth-Token": unscoped_token},
        )
        resp.raise_for_status()
        return resp.json().get("projects", [])


async def _get_user_default_project_id(unscoped_token: str, user_id: str) -> str:
    """unscoped 토큰으로 사용자의 default_project_id를 비동기로 조회.

    Keystone GET /v3/users/{user_id}. 실패 또는 미설정 시 빈 문자열을 반환한다.
    """
    if not user_id:
        return ""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10, verify=settings.ssl_verify) as client:
            resp = await client.get(
                f"{settings.os_auth_url}/users/{user_id}",
                headers={"X-Auth-Token": unscoped_token},
            )
            resp.raise_for_status()
            user = resp.json().get("user", {})
            return user.get("default_project_id") or ""
    except Exception:
        logger.warning("default_project_id 조회 실패", exc_info=True)
        return ""


async def _scope_token(unscoped_token: str, project_id: str) -> dict:
    """unscoped 토큰을 특정 프로젝트로 scope → scoped 토큰과 정보 반환."""
    settings = get_settings()
    body = {
        "auth": {
            "identity": {
                "methods": ["token"],
                "token": {"id": unscoped_token},
            },
            "scope": {
                "project": {"id": project_id},
            },
        }
    }
    async with httpx.AsyncClient(timeout=30, verify=settings.ssl_verify) as client:
        resp = await client.post(
            f"{settings.os_auth_url}/auth/tokens",
            json=body,
        )
        resp.raise_for_status()
        scoped_token = resp.headers.get("X-Subject-Token", "")
        if not scoped_token:
            raise ValueError("Keystone scope 응답에 X-Subject-Token 없음")
        token_data = resp.json().get("token", {})
        return {
            "token": scoped_token,
            "project_id": token_data.get("project", {}).get("id", ""),
            "project_name": token_data.get("project", {}).get("name", ""),
            "user_id": token_data.get("user", {}).get("id", ""),
            "username": token_data.get("user", {}).get("name", ""),
            "expires_at": token_data.get("expires_at", ""),
            "roles": [r["name"] for r in token_data.get("roles", [])],
        }


async def exchange_code(code: str, state: str) -> dict:
    """
    GitLab OAuth2 authorization code를 Keystone 토큰으로 교환.
    TokenResponse 호환 dict 반환.

    사용자의 default_project_id가 접근 가능한 프로젝트 목록에 포함되어 있으면
    해당 프로젝트로 scope, 그렇지 않으면 첫 번째 프로젝트로 fallback.
    프로젝트 목록 조회와 default_project_id 조회를 병렬로 수행한다.
    """
    import base64
    import json as _json

    expected_nonce = await _validate_state(state)

    tokens = await _exchange_gitlab_code(code)

    # id_token nonce 검증 (replay 공격 방지)
    id_token = tokens["id_token"]
    parts = id_token.split(".")
    if len(parts) >= 2:
        payload_b64 = parts[1] + "=="
        try:
            token_payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            token_nonce = token_payload.get("nonce")
            if expected_nonce and token_nonce != expected_nonce:
                raise ValueError("OIDC nonce 불일치 — 토큰 재생 공격 의심")
        except (ValueError, KeyError):
            raise
        except Exception:
            logger.warning("id_token nonce 검증 실패 (파싱 오류)", exc_info=True)

    fed = await _federated_auth(id_token)
    unscoped_token = fed["token"]
    user_id = fed.get("user", {}).get("id", "")

    projects, default_pid = await asyncio.gather(
        _list_projects_for_token(unscoped_token),
        _get_user_default_project_id(unscoped_token, user_id),
    )
    if not projects:
        raise ValueError("접근 가능한 프로젝트가 없습니다")

    valid_default_pid = default_pid if default_pid and any(p["id"] == default_pid for p in projects) else ""
    target_pid = valid_default_pid or projects[0]["id"]
    scoped = await _scope_token(unscoped_token, target_pid)
    scoped["default_project_id"] = valid_default_pid
    return scoped
