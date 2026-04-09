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

import logging
import secrets
import urllib.parse
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


_STATE_TTL = 600  # 10분


async def _get_redis():
    from app.services.cache import _get_redis as _cache_redis
    return await _cache_redis()


async def get_authorize_url() -> str:
    """GitLab OAuth2 authorize URL을 생성하고 state를 Redis에 저장."""
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    r = await _get_redis()
    await r.setex(f"union:gitlab_state:{state}", _STATE_TTL, "1")

    params = {
        "client_id": settings.gitlab_oidc_client_id,
        "redirect_uri": settings.gitlab_oidc_redirect_uri,
        "response_type": "code",
        "scope": settings.gitlab_oidc_scopes,
        "state": state,
    }
    query = urllib.parse.urlencode(params)
    return f"{settings.gitlab_oidc_gitlab_url}/oauth/authorize?{query}"


async def _validate_state(state: str) -> None:
    """Redis에서 state 검증 후 삭제. 없거나 Redis 오류면 예외 발생."""
    r = await _get_redis()
    key = f"union:gitlab_state:{state}"
    val = await r.get(key)
    if val is None:
        raise ValueError("유효하지 않거나 만료된 state입니다")
    await r.delete(key)


async def _exchange_gitlab_code(code: str) -> dict:
    """GitLab 토큰 엔드포인트에서 authorization code를 토큰으로 교환."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30, verify=True) as client:
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
    async with httpx.AsyncClient(timeout=30, verify=True) as client:
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
    async with httpx.AsyncClient(timeout=30, verify=True) as client:
        resp = await client.get(
            f"{settings.os_auth_url}/auth/projects",
            headers={"X-Auth-Token": unscoped_token},
        )
        resp.raise_for_status()
        return resp.json().get("projects", [])


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
    async with httpx.AsyncClient(timeout=30, verify=True) as client:
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
    """
    await _validate_state(state)

    tokens = await _exchange_gitlab_code(code)
    fed = await _federated_auth(tokens["id_token"])
    unscoped_token = fed["token"]

    projects = await _list_projects_for_token(unscoped_token)
    if not projects:
        raise ValueError("접근 가능한 프로젝트가 없습니다")

    first_project_id = projects[0]["id"]
    return await _scope_token(unscoped_token, first_project_id)
