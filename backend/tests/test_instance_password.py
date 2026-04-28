"""인스턴스 관리자 패스워드 재설정 API 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


def _make_server(status: str = "ACTIVE", image_id: str = "img-1") -> MagicMock:
    s = MagicMock()
    s.id = "server-1"
    s.name = "test-server"
    s.status = status
    s.image = {"id": image_id} if image_id else {}
    s.addresses = {}
    s.metadata = {}
    s.flavor = {"id": "flv-1"}
    s.created_at = None
    s.key_name = None
    s.user_id = "u1"
    s.project_id = "p1"
    s.tenant_id = None
    s.fault = None
    return s


def _qga_meta(enabled: bool = True, admin_user: str = "ubuntu") -> dict:
    return {
        "qga_enabled": enabled,
        "os_admin_user": admin_user if enabled else None,
        "image_id": "img-1",
        "image_name": "Ubuntu 22.04",
    }


@pytest.mark.asyncio
async def test_precheck_returns_supported_when_active_and_qga(admin_client, mock_conn):
    """ACTIVE + QGA 지원 시 supported=True를 반환한다."""
    mock_conn.compute.get_server.return_value = _make_server()
    with patch("app.api.compute.instances.nova.get_server_image_meta", return_value=_qga_meta(True)):
        resp = await admin_client.get("/api/instances/server-1/admin-password/precheck")
    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is True
    assert data["os_admin_user"] == "ubuntu"
    assert data["server_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_precheck_returns_unsupported_when_not_active(admin_client, mock_conn):
    """ACTIVE가 아닌 인스턴스는 supported=False를 반환한다."""
    mock_conn.compute.get_server.return_value = _make_server(status="SHELVED")
    with patch("app.api.compute.instances.nova.get_server_image_meta", return_value=_qga_meta(True)):
        resp = await admin_client.get("/api/instances/server-1/admin-password/precheck")
    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is False
    assert "ACTIVE" in data["reason"]


@pytest.mark.asyncio
async def test_precheck_returns_unsupported_when_no_qga(admin_client, mock_conn):
    """QGA 미지원 이미지는 supported=False를 반환한다."""
    mock_conn.compute.get_server.return_value = _make_server()
    with patch("app.api.compute.instances.nova.get_server_image_meta", return_value=_qga_meta(False)):
        resp = await admin_client.get("/api/instances/server-1/admin-password/precheck")
    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is False
    assert "QGA" in data["reason"]


@pytest.mark.asyncio
async def test_precheck_requires_admin(non_admin_client):
    """비관리자는 precheck 엔드포인트에 접근 불가 (403)."""
    resp = await non_admin_client.get("/api/instances/server-1/admin-password/precheck")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_password_success(admin_client, mock_conn):
    """정상 케이스: change_server_password가 정확히 한 번 호출된다."""
    mock_conn.compute.get_server.return_value = _make_server()
    with (
        patch("app.api.compute.instances.nova.get_server_image_meta", return_value=_qga_meta(True)),
        patch("app.api.compute.instances.nova.change_server_password") as mock_chpw,
    ):
        resp = await admin_client.post(
            "/api/instances/server-1/admin-password",
            json={"new_password": "Secure1234!"},
        )
    assert resp.status_code == 204
    mock_chpw.assert_called_once()
    _, call_server_id, call_password = mock_chpw.call_args.args
    assert call_server_id == "server-1"
    assert call_password == "Secure1234!"


@pytest.mark.asyncio
async def test_set_password_requires_admin(non_admin_client):
    """비관리자는 패스워드 변경 불가 (403)."""
    resp = await non_admin_client.post(
        "/api/instances/server-1/admin-password",
        json={"new_password": "Secure1234!"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_set_password_rejects_non_active(admin_client, mock_conn):
    """ACTIVE가 아닌 인스턴스에 패스워드 변경 시도 시 409를 반환한다."""
    mock_conn.compute.get_server.return_value = _make_server(status="SHUTOFF")
    resp = await admin_client.post(
        "/api/instances/server-1/admin-password",
        json={"new_password": "Secure1234!"},
    )
    assert resp.status_code == 409
    assert "ACTIVE" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_password_rejects_no_qga(admin_client, mock_conn):
    """QGA 미지원 이미지에 패스워드 변경 시도 시 409를 반환한다."""
    mock_conn.compute.get_server.return_value = _make_server()
    with patch("app.api.compute.instances.nova.get_server_image_meta", return_value=_qga_meta(False)):
        resp = await admin_client.post(
            "/api/instances/server-1/admin-password",
            json={"new_password": "Secure1234!"},
        )
    assert resp.status_code == 409
    assert "QGA" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_set_password_rejects_short_password(admin_client, mock_conn):
    """8자 미만 패스워드는 422를 반환한다."""
    resp = await admin_client.post(
        "/api/instances/server-1/admin-password",
        json={"new_password": "short"},
    )
    assert resp.status_code == 422
