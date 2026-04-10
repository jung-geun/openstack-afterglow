"""공통 테스트 픽스처."""
import os
os.environ.setdefault("UNION_ALLOW_INSECURE", "1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_os_conn


def make_mock_conn(project_id: str = "test-project-123") -> MagicMock:
    """모의 OpenStack Connection 객체 생성."""
    conn = MagicMock()
    conn._union_token = "test-token"
    conn._union_project_id = project_id
    conn.close = MagicMock()
    return conn


@pytest.fixture
def mock_conn():
    return make_mock_conn()


@pytest.fixture
async def client(mock_conn):
    """인증 의존성을 모의 객체로 오버라이드한 AsyncClient."""
    async def override_get_os_conn():
        try:
            yield mock_conn
        finally:
            pass

    app.dependency_overrides[get_os_conn] = override_get_os_conn
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Auth-Token": "test-token", "X-Project-Id": "test-project-123"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
