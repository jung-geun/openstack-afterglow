"""프로필 API 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def make_user_obj(user_id: str = "test-user-123", name: str = "testuser") -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.name = name
    u.email = "test@example.com"
    u.description = "test user"
    u.default_project_id = "test-project-123"
    return u


@pytest.mark.asyncio
async def test_get_profile(client, mock_conn):
    mock_conn.identity.get_user.return_value = make_user_obj()
    resp = await client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test-user-123"
    assert data["name"] == "testuser"


@pytest.mark.asyncio
async def test_update_profile(client, mock_conn):
    updated = make_user_obj()
    updated.email = "new@example.com"
    mock_conn.identity.update_user.return_value = updated
    resp = await client.patch("/api/profile", json={"email": "new@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_update_profile_no_fields(client, mock_conn):
    """수정할 항목 없으면 400."""
    resp = await client.patch("/api/profile", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_change_password(client, mock_conn):
    mock_conn.identity.update_user.return_value = make_user_obj()
    with patch("app.api.identity.profile.keystone.authenticate", return_value={}):
        resp = await client.post(
            "/api/profile/password",
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "changed"


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, mock_conn):
    """현재 패스워드 불일치 시 401."""
    with patch("app.api.identity.profile.keystone.authenticate", side_effect=Exception("auth failed")):
        resp = await client.post(
            "/api/profile/password",
            json={
                "current_password": "WrongPass",
                "new_password": "NewPass456!",
            },
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.patch("/api/profile", json={"email": "x@x.com"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/profile/password", json={"current_password": "a", "new_password": "b"})
    assert resp.status_code == 401
