"""Grafana 임베드용 JWT 발급 엔드포인트."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_token_info
from app.config import get_settings

router = APIRouter()

_TOKEN_TTL = 3600  # 1시간


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _create_grafana_jwt(
    user_id: str,
    username: str,
    project_id: str,
    secret: str,
    ttl: int = _TOKEN_TTL,
) -> str:
    """Grafana auth.jwt 호환 HS256 JWT 발급."""
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": user_id,
                "login": username,
                "name": username,
                "email": f"{username}@afterglow",
                "role": "Viewer",
                "project_id": project_id,
                "iat": now,
                "exp": now + ttl,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


@router.post("/token")
async def issue_grafana_token(
    token_info: dict = Depends(get_token_info),
):
    """현재 로그인 사용자를 위한 Grafana 임베드 JWT 발급.

    반환값:
    - `token`: Grafana X-JWT-Assertion 헤더에 사용할 JWT
    - `grafana_url`: Grafana iframe용 기본 URL
    - `expires_in`: 유효 시간(초)
    """
    settings = get_settings()
    if not settings.grafana_jwt_secret:
        raise HTTPException(status_code=503, detail="grafana_jwt_secret이 설정되지 않았습니다")

    token = _create_grafana_jwt(
        user_id=token_info["user_id"],
        username=token_info["username"],
        project_id=token_info["project_id"],
        secret=settings.grafana_jwt_secret,
    )
    return {
        "token": token,
        "grafana_url": settings.grafana_base_url,
        "expires_in": _TOKEN_TTL,
    }
