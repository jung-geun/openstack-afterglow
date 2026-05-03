"""common/metrics.py 엔드포인트 단위 테스트.

metrics 라우터는 deps.require_admin (is_system_admin 기반) 을 사용한다.

테스트:
1. 인증 없음 → 401
2. system admin → 200
3. admin role 없는 사용자 → 403
4. is_system_admin=False 인 프로젝트 admin → 403
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_os_conn, get_token_info
from app.main import app


@pytest.mark.asyncio
async def test_metrics_requires_auth():
    """인증 없이 /api/metrics 접근 → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/metrics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metrics_allowed_for_admin(admin_client):
    """admin role 보유 사용자 → 200 (prometheus 텍스트 형식)."""
    resp = await admin_client.get("/api/metrics")
    assert resp.status_code != 403


@pytest.mark.asyncio
async def test_metrics_forbidden_for_member(non_admin_client):
    """member 역할만 가진 사용자 → 403."""
    resp = await non_admin_client.get("/api/metrics")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_metrics_blocks_project_admin_without_system_admin(mock_conn):
    """프로젝트 admin (is_system_admin=False, roles=['admin']) → 403."""
    from tests.conftest import make_token_info

    async def _override_conn():
        try:
            yield mock_conn
        finally:
            pass

    async def _override_token():
        return make_token_info(roles=["admin"], is_system_admin=False)

    app.dependency_overrides[get_os_conn] = _override_conn
    app.dependency_overrides[get_token_info] = _override_token
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Auth-Token": "test-token", "X-Project-Id": "test-project-123"},
        ) as ac:
            resp = await ac.get("/api/metrics")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
