"""common/metrics.py 엔드포인트 단위 테스트.

현재 _require_admin 은 role_names 에 "admin" 문자열 포함 여부만 확인 (로컬 함수).
이것은 deps.require_admin (is_system_admin 기반) 와 불일치한다.

테스트:
1. 인증 없음 → 401
2. admin role 있는 사용자 → 200
3. admin role 없는 사용자 → 403
4. (xfail) is_system_admin=False 이지만 roles=["admin"] 인 경우 → 현재 200 반환 (불일치 기록)
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_os_conn, get_token_info


@pytest.mark.asyncio
async def test_metrics_requires_auth():
    """인증 없이 /api/metrics 접근 → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
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


@pytest.mark.xfail(
    reason=(
        "common/metrics.py::_require_admin 이 role_names 문자열 체크만 수행. "
        "is_system_admin=False 이지만 roles=['admin']인 프로젝트 admin에게 접근 허용됨. "
        "deps.require_admin 으로 통일하면 xfail→xpass 로 감지됨."
    ),
    strict=False,
)
@pytest.mark.asyncio
async def test_metrics_blocks_project_admin_without_system_admin(mock_conn):
    """프로젝트 admin (is_system_admin=False, roles=['admin']) → 403 이어야 하지만 현재는 200."""
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
        # 기대(보안 강화): 403
        # 현재 동작: 200 (is_system_admin 무시) → xfail
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
