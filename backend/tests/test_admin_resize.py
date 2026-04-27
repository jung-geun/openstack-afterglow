"""인스턴스 resize / revert-resize 관리자 API 단위 테스트."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_admin_resize_calls_nova(admin_client, mock_conn):
    """resize 엔드포인트가 nova.resize_server를 올바른 인자로 호출한다."""
    with (
        patch("app.api.identity.admin.nova.resize_server") as mock_resize,
        patch("app.api.identity.admin.invalidate"),
    ):
        resp = await admin_client.post(
            "/api/admin/instances/inst-1/resize",
            json={"flavor_id": "flavor-new"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resizing"
    mock_resize.assert_called_once_with(mock_conn, "inst-1", "flavor-new")


@pytest.mark.asyncio
async def test_admin_resize_requires_admin(non_admin_client):
    """일반 사용자는 resize 엔드포인트에 접근 불가 (403)."""
    resp = await non_admin_client.post(
        "/api/admin/instances/inst-1/resize",
        json={"flavor_id": "flavor-new"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_revert_resize_calls_nova(admin_client, mock_conn):
    """revert-resize 엔드포인트가 nova.revert_resize_server를 호출한다."""
    with (
        patch("app.api.identity.admin.nova.revert_resize_server") as mock_revert,
        patch("app.api.identity.admin.invalidate"),
    ):
        resp = await admin_client.post("/api/admin/instances/inst-1/revert-resize")
    assert resp.status_code == 200
    assert resp.json()["status"] == "reverting"
    mock_revert.assert_called_once_with(mock_conn, "inst-1")


@pytest.mark.asyncio
async def test_admin_resize_nova_failure_returns_400(admin_client, mock_conn):
    """Nova 오류 시 400을 반환한다."""
    with patch("app.api.identity.admin.nova.resize_server", side_effect=Exception("Nova error")):
        resp = await admin_client.post(
            "/api/admin/instances/inst-1/resize",
            json={"flavor_id": "flavor-new"},
        )
    assert resp.status_code == 400
