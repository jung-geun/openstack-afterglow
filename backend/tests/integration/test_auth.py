"""인증 및 세션 관련 통합 테스트."""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(anon_client, credentials):
    resp = await anon_client.post("/api/auth/login", json=credentials)
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "project_id" in data
    assert data["username"] == credentials["username"]
    assert len(data["roles"]) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_login_bad_password(anon_client, credentials):
    bad = {**credentials, "password": "wrong-password-12345"}
    resp = await anon_client.post("/api/auth/login", json=bad)
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_me(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    assert "username" in data
    assert "roles" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_session_info(client):
    resp = await client.get("/api/auth/session-info")
    assert resp.status_code == 200
    data = resp.json()
    assert "remaining_seconds" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_extend_session(client):
    resp = await client.post("/api/auth/extend-session")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_list_projects(client):
    resp = await client.get("/api/auth/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_no_token_returns_401(anon_client):
    resp = await anon_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_gitlab_enabled(anon_client):
    resp = await anon_client.get("/api/auth/gitlab/enabled")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
