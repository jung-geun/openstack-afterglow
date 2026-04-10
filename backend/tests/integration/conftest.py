"""
통합 테스트 공통 픽스처.

config.toml의 실제 OpenStack 인증 정보를 사용하여 로그인 후 토큰을 획득하고,
httpx AsyncClient로 FastAPI 앱에 실제 요청을 보낸다.

사전 조건:
  - Redis 실행 중 (config.toml의 redis_url)
  - OpenStack 접근 가능 (config.toml의 openstack 섹션)
  - 환경변수 UNION_ALLOW_INSECURE=1 (개발 시크릿 키 허용)

실행:
  cd backend
  UNION_ALLOW_INSECURE=1 uv run pytest tests/integration/ -v
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

# 환경변수는 루트 tests/conftest.py에서 설정됨

from app.main import app
from app.config import get_settings


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def credentials(settings):
    """config.toml에서 관리자 인증 정보를 가져온다."""
    return {
        "username": settings.os_username,
        "password": settings.os_password,
        "project_name": settings.os_project_name,
        "domain_name": settings.os_user_domain_name,
    }


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def auth_data(credentials):
    """실제 Keystone 로그인으로 토큰을 획득한다. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/auth/login", json=credentials)
        assert resp.status_code == 200, f"로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
def token(auth_data):
    return auth_data["token"]


@pytest.fixture(scope="session")
def project_id(auth_data):
    return auth_data["project_id"]


@pytest.fixture(scope="session")
def auth_headers(token, project_id):
    """인증 헤더 dict."""
    return {
        "X-Auth-Token": token,
        "X-Project-Id": project_id,
    }


@pytest.fixture(scope="session")
async def client(auth_headers):
    """인증 헤더가 포함된 AsyncClient. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers,
        timeout=30,
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def anon_client():
    """인증 없는 AsyncClient (공개 엔드포인트 테스트용)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30,
    ) as ac:
        yield ac
