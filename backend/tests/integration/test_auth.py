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


# ─────────────────────────────────────────────────────────────────
# PR4: is_system_admin 분리 검증 — sanity check
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_login_is_system_admin(admin_auth_data):
    """admin 로그인 응답의 is_system_admin=True 확인. 실패 시 credentials.toml [admin] 확인."""
    assert admin_auth_data.get("is_system_admin") is True, (
        "admin 계정이 is_system_admin=False — "
        "credentials.toml [admin] 계정이 실제 system admin role을 보유하는지 확인"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_user_login_is_not_system_admin(user_auth_data):
    """일반 유저 로그인 응답의 is_system_admin=False 확인. 실패 시 credentials.toml [user] 확인."""
    assert user_auth_data.get("is_system_admin") is False, (
        "일반 유저가 is_system_admin=True — "
        "credentials.toml [user] 계정이 system admin role을 보유하지 않는지 확인"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_user_session_info(user_client):
    """일반 유저도 세션 정보를 조회할 수 있어야 한다."""
    resp = await user_client.get("/api/auth/session-info")
    assert resp.status_code == 200
    assert "remaining_seconds" in resp.json()


# ─────────────────────────────────────────────────────────────────
# admin_user 검증 (admin 프로젝트 admin role 보유, default project ≠ admin 가능)
# credentials.toml [admin_user] 또는 UNION_TEST_ADMIN_USER_* 환경변수 필요
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_user_login_is_system_admin(admin_user_auth_data):
    """admin_user 로그인 응답의 is_system_admin=True 확인.

    scoped token 의 project 가 admin 이 아니더라도,
    admin 프로젝트에 admin role 이 있으면 True 여야 한다.
    실패 시 credentials.toml [admin_user] 계정 role 확인.
    """
    assert admin_user_auth_data.get("is_system_admin") is True, (
        "admin_user 가 is_system_admin=False — "
        "credentials.toml [admin_user] 계정이 admin 프로젝트에서 admin role을 보유하는지 확인"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_user_me_returns_is_system_admin(admin_user_client):
    """/api/auth/me 응답에도 is_system_admin=True 가 포함돼야 한다.

    페이지 새로고침 시 localStorage 재동기화에 사용되는 엔드포인트.
    실패 시 백엔드 UserInfo 모델 또는 /me 핸들러 is_system_admin 반환 확인.
    """
    resp = await admin_user_client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("is_system_admin") is True, (
        "/api/auth/me 응답에 is_system_admin=True 없음 — "
        "UserInfo 모델과 me() 핸들러가 is_system_admin 을 반환하는지 확인"
    )
