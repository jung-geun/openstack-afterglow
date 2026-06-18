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
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "password123",
                "project_name": "test-project",
                "domain_name": "Default",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] and data["token"].count(".") == 2  # JWT: header.payload.sig
    assert data["user_id"] == "test-user-123"


@pytest.mark.asyncio
async def test_login_failure(client):
    with patch("app.api.identity.auth.keystone.authenticate", side_effect=Exception("auth failed")):
        resp = await client.post(
            "/api/v1/auth/login",
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
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "test-user-123"
    assert data["username"] == "testuser"


# ────── token/project (rescope) ──────


@pytest.mark.asyncio
async def test_scope_project(client):
    """POST /api/auth/token/project: 접근 가능한 프로젝트로 새 토큰 쌍 발급."""
    kc_info = {
        "token": "new-ks-token",
        "project_id": "other-project-456",
        "project_name": "other-project",
        "user_id": "test-user-123",
        "username": "testuser",
        "roles": ["member"],
        "is_system_admin": False,
    }
    with (
        patch("app.api.identity.auth.keystone.validate_token", return_value=kc_info),
        patch("app.api.identity.auth.record_project_access", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/v1/auth/token/project",
            json={"project_id": "other-project-456"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "other-project-456"
    assert data["token"] and data["token"].count(".") == 2


@pytest.mark.asyncio
async def test_scope_project_no_access(client):
    """접근 권한 없는 프로젝트로 rescope 시 403."""
    with patch(
        "app.api.identity.auth.keystone.validate_token",
        side_effect=Exception("forbidden"),
    ):
        resp = await client.post(
            "/api/v1/auth/token/project",
            json={"project_id": "forbidden-project"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scope_project_old_route_gone(client):
    """구 /switch-project 경로는 더 이상 처리되지 않아야 한다 (404 또는 405)."""
    resp = await client.post(
        "/api/v1/auth/switch-project",
        json={"project_id": "any-project"},
    )
    assert resp.status_code in (404, 405), f"구 /switch-project가 예상치 못한 {resp.status_code}를 반환했습니다"


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
        resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert "로그아웃" in resp.json()["message"]


@pytest.mark.asyncio
async def test_logout_invalidates_token_cache(client):
    """logout 호출 시 invalidate_token_cache 가 호출되어 검증 캐시가 즉시 비워져야 한다."""
    with (
        patch("app.api.identity.auth.keystone.revoke_token", return_value=None),
        patch(
            "app.api.identity.auth.invalidate_token_cache",
            new_callable=AsyncMock,
        ) as mock_invalidate,
    ):
        resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    # invalidate_token_cache 가 호출되어야 함 (token, project_id 인자)
    assert mock_invalidate.await_count == 1
    args, _ = mock_invalidate.await_args
    assert args[0]  # token 비어있지 않음


def test_token_cache_ttl_is_short():
    """토큰 검증 캐시 TTL 이 60초 이하인지 (revoke window 제한)."""
    from app.api import deps

    assert deps._TOKEN_CACHE_TTL <= 60, (
        f"토큰 캐시 TTL 이 {deps._TOKEN_CACHE_TTL}s 으로 너무 길다 — revoke 후 공격 window 가 벌어짐"
    )


# ────── projects ──────


@pytest.mark.asyncio
async def test_list_projects(client):
    projects = [{"id": "proj-1", "name": "myproject", "description": "", "domain_id": "default", "enabled": True}]
    with patch("app.api.identity.auth.keystone.list_projects", return_value=projects):
        resp = await client.get("/api/v1/auth/projects")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "proj-1"


# ────── groups ──────


@pytest.mark.asyncio
async def test_list_my_groups_success(client):
    groups = [{"id": "grp-1", "name": "devteam", "description": "Dev Team", "domain_id": "default"}]
    with patch("app.api.identity.auth.keystone.list_user_groups", return_value=groups):
        resp = await client.get("/api/v1/auth/groups")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "grp-1"
    assert resp.json()[0]["name"] == "devteam"


@pytest.mark.asyncio
async def test_list_my_groups_forbidden(client):
    with patch("app.api.identity.auth.keystone.list_user_groups", side_effect=PermissionError("forbidden")):
        resp = await client.get("/api/v1/auth/groups")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_my_groups_unexpected_error_returns_empty(client):
    # service 내부에서 어떤 예외든 PermissionError 로 변환되므로 endpoint 는 [] 반환
    with patch("app.api.identity.auth.keystone.list_user_groups", side_effect=PermissionError("unexpected")):
        resp = await client.get("/api/v1/auth/groups")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_user_groups_converts_exception_to_permission_error():
    """keystone client 가 임의 예외를 raise 해도 service 가 PermissionError 로 변환하는지 검증."""
    from unittest.mock import MagicMock

    mock_ks = MagicMock()
    mock_ks.groups.list.side_effect = RuntimeError("kaboom")

    with (
        patch("app.services.keystone.get_settings") as mock_cfg,
        patch("app.services.keystone.v3.Token"),
        patch("app.services.keystone.ks_session.Session"),
        patch("keystoneclient.v3.client.Client", return_value=mock_ks),
    ):
        mock_cfg.return_value.os_auth_url = "http://keystone:5000/v3"
        mock_cfg.return_value.ssl_verify = False
        import pytest as _pytest

        from app.services.keystone import list_user_groups

        with _pytest.raises(PermissionError):
            list_user_groups("fake-token", "fake-user-id")


# ────── GitLab enabled ──────


@pytest.mark.asyncio
async def test_gitlab_enabled(client):
    resp = await client.get("/auth/gitlab/enabled")
    assert resp.status_code == 200
    assert "enabled" in resp.json()


# ────── auth_method 필드 ──────


@pytest.mark.asyncio
async def test_me_returns_auth_method(client):
    """/me 응답에 auth_method 필드가 포함되어야 한다."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_method" in data
    assert data["auth_method"] == "password"  # 기본 로컬 로그인


@pytest.mark.asyncio
async def test_gitlab_callback_stores_federated_auth_method():
    """gitlab_callback이 store_session에 auth_method='federated'를 전달하는지 확인."""
    exchange_data = {
        "token": "ks-token",
        "project_id": "proj-123",
        "project_name": "test-project",
        "user_id": "user-123",
        "username": "gitlabuser",
        "roles": ["member"],
        "is_system_admin": False,
    }
    captured: dict = {}

    async def mock_store_session(*, jti, keystone_token, project_id, user_id, exp, auth_method="password", **kwargs):
        captured["auth_method"] = auth_method

    with (
        # exchange_code는 함수 내에서 지연 import되므로 원본 모듈에서 패치
        patch("app.services.gitlab_oidc.exchange_code", new_callable=AsyncMock, return_value=exchange_data),
        patch("app.services.session_store.store_session", side_effect=mock_store_session),
        patch("app.services.jwt_service.sign_refresh", return_value=("refresh-tok", "jti-123", 9999999999)),
        patch("app.services.jwt_service.sign_access", return_value=("access-tok", "ajti-123", 9999999999)),
        patch("app.api.identity.auth._prewarm_dashboard"),
        patch("app.api.identity.auth.record_project_access", new_callable=AsyncMock),
    ):
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/auth/gitlab/callback",
                json={"code": "auth-code", "state": "state-value"},
            )

    # GitLab OIDC 비활성화 시 404 — 그 외엔 store_session 호출 여부만 검증
    if resp.status_code != 404:
        assert captured.get("auth_method") == "federated", (
            f"gitlab_callback은 auth_method='federated'를 store_session에 전달해야 합니다. "
            f"실제 값: {captured.get('auth_method')!r}"
        )
