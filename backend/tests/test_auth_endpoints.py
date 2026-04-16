"""인증 API 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_auth_data() -> dict:
    return {
        "token": "test-token",
        "project_id": "test-project-123",
        "project_name": "test-project",
        "user_id": "test-user-123",
        "username": "testuser",
        "expires_at": "2099-01-01T00:00:00Z",
        "roles": ["member"],
    }


def make_user_obj() -> MagicMock:
    u = MagicMock()
    u.id = "test-user-123"
    u.name = "testuser"
    u.default_project_id = "test-project-123"
    return u


# ────── 로그인 ──────


@pytest.mark.asyncio
async def test_login_success(client):
    mock_conn = MagicMock()
    mock_conn.identity.get_user.return_value = make_user_obj()

    with (
        patch("app.api.identity.auth.keystone.authenticate", return_value=make_auth_data()),
        patch("app.api.identity.auth.keystone.get_openstack_connection", return_value=mock_conn),
    ):
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "password123",
                "project_name": "test-project",
                "domain_name": "Default",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "test-token"
    assert data["user_id"] == "test-user-123"


@pytest.mark.asyncio
async def test_login_failure(client):
    with patch("app.api.identity.auth.keystone.authenticate", side_effect=Exception("auth failed")):
        resp = await client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "wrongpassword",
                "project_name": "test-project",
                "domain_name": "Default",
            },
        )
    assert resp.status_code == 401


# ────── /me ──────


@pytest.mark.asyncio
async def test_me(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "test-user-123"
    assert data["username"] == "testuser"


# ────── session-info ──────


@pytest.mark.asyncio
async def test_session_info(client):
    with patch("app.api.identity.auth.get_session_remaining", new_callable=AsyncMock, return_value=3500):
        resp = await client.get("/api/auth/session-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "remaining_seconds" in data
    assert "timeout_seconds" in data


# ────── extend-session ──────


@pytest.mark.asyncio
async def test_extend_session(client):
    with patch("app.api.identity.auth.extend_session", new_callable=AsyncMock):
        resp = await client.post("/api/auth/extend-session")
    assert resp.status_code == 200
    assert "message" in resp.json()


# ────── logout ──────


@pytest.mark.asyncio
async def test_logout(client):
    with (
        patch("app.api.identity.auth.keystone.revoke_token", return_value=None),
        patch("app.services.cache._get_redis") as mock_redis,
    ):
        mock_r = AsyncMock()
        mock_r.delete = AsyncMock()
        mock_redis.return_value = mock_r
        resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert "로그아웃" in resp.json()["message"]


# ────── projects ──────


@pytest.mark.asyncio
async def test_list_projects(client):
    projects = [{"id": "proj-1", "name": "myproject", "description": "", "domain_id": "default", "enabled": True}]
    with patch("app.api.identity.auth.keystone.list_projects", return_value=projects):
        resp = await client.get("/api/auth/projects")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "proj-1"


# ────── GitLab enabled ──────


@pytest.mark.asyncio
async def test_gitlab_enabled(client):
    resp = await client.get("/api/auth/gitlab/enabled")
    assert resp.status_code == 200
    assert "enabled" in resp.json()
