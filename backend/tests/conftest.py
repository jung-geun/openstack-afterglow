"""공통 테스트 픽스처."""

import os

os.environ.setdefault("AFTERGLOW_ALLOW_INSECURE", "1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SERVICE_MANILA_ENABLED", "true")
os.environ.setdefault("SERVICE_MAGNUM_ENABLED", "true")
os.environ.setdefault("SERVICE_ZUN_ENABLED", "true")
os.environ.setdefault("SERVICE_K3S_ENABLED", "true")

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_os_conn, get_token_info
from app.main import app


def make_mock_conn(project_id: str = "test-project-123") -> MagicMock:
    """모의 OpenStack Connection 객체 생성."""
    conn = MagicMock()
    conn._afterglow_token = "test-token"
    conn._afterglow_project_id = project_id
    conn._afterglow_user_id = "test-user-123"
    conn.close = MagicMock()
    return conn


def make_token_info(
    roles: list[str] | None = None,
    project_id: str = "test-project-123",
    is_system_admin: bool = False,
) -> dict:
    """모의 token_info 딕셔너리 생성."""
    return {
        "token": "test-token",
        "project_id": project_id,
        "project_name": "test-project",
        "user_id": "test-user-123",
        "username": "testuser",
        "roles": roles or ["member"],
        "expires_at": "2099-01-01T00:00:00Z",
        "is_system_admin": is_system_admin,
    }


@pytest.fixture
def mock_conn():
    return make_mock_conn()


@pytest.fixture
async def client(mock_conn):
    """인증 의존성을 모의 객체로 오버라이드한 AsyncClient (일반 사용자)."""

    async def override_get_os_conn():
        try:
            yield mock_conn
        finally:
            pass

    async def override_get_token_info():
        return make_token_info(roles=["member"])

    app.dependency_overrides[get_os_conn] = override_get_os_conn
    app.dependency_overrides[get_token_info] = override_get_token_info
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Auth-Token": "test-token", "X-Project-Id": "test-project-123"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(mock_conn):
    """admin 역할을 가진 인증 모의 객체로 오버라이드한 AsyncClient."""

    async def override_get_os_conn():
        try:
            yield mock_conn
        finally:
            pass

    async def override_get_token_info():
        return make_token_info(roles=["admin", "member"], is_system_admin=True)

    app.dependency_overrides[get_os_conn] = override_get_os_conn
    app.dependency_overrides[get_token_info] = override_get_token_info
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Auth-Token": "test-token", "X-Project-Id": "test-project-123"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def non_admin_client(mock_conn):
    """admin 역할 없이 member 역할만 가진 AsyncClient (403 테스트용)."""

    async def override_get_os_conn():
        try:
            yield mock_conn
        finally:
            pass

    async def override_get_token_info():
        return make_token_info(roles=["member"])

    app.dependency_overrides[get_os_conn] = override_get_os_conn
    app.dependency_overrides[get_token_info] = override_get_token_info
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Auth-Token": "test-token", "X-Project-Id": "test-project-123"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
