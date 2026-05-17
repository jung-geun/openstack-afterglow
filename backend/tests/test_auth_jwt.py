"""JWT access+refresh 토큰 통합 단위 테스트."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis as fakeredis
import pytest

# ──────────────────────────────────────────────────────────────────
# 공통 픽스처 / 헬퍼
# ──────────────────────────────────────────────────────────────────

_KEYSTONE_TOKEN = "ks-token-abcdefg"
_KS_DATA = {
    "token": _KEYSTONE_TOKEN,
    "project_id": "proj-1",
    "project_name": "myproject",
    "user_id": "user-1",
    "username": "alice",
    "expires_at": "2099-01-01T00:00:00+00:00",
    "roles": ["member"],
    "is_system_admin": False,
}


def _make_fake_redis():
    return fakeredis.FakeRedis()


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    """모든 테스트에서 fakeredis를 사용하도록 패치."""
    fake = _make_fake_redis()

    async def _get_fake():
        return fake

    monkeypatch.setattr("app.services.cache._get_redis", _get_fake)
    return fake


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """테스트용 짧은 TTL 설정."""
    from app.config import Settings

    s = Settings.model_construct(
        secret_key="test-secret-key-for-jwt-tests",
        jwt_access_ttl=900,
        jwt_refresh_ttl=604800,
        session_timeout_seconds=3600,
        session_warning_before_seconds=300,
        session_absolute_timeout=14400,
    )
    monkeypatch.setattr("app.config.get_settings", lambda: s)
    monkeypatch.setattr("app.services.jwt_service.get_settings", lambda: s)
    monkeypatch.setattr("app.services.session_store.get_settings", lambda: s, raising=False)


# ──────────────────────────────────────────────────────────────────
# jwt_service 단위 테스트
# ──────────────────────────────────────────────────────────────────

class TestJwtService:
    def test_access_roundtrip(self):
        from app.services.jwt_service import sign_access, verify_access

        token, jti, exp = sign_access(
            user_id="u1",
            username="alice",
            project_id="p1",
            project_name="proj",
            roles=["member"],
            is_system_admin=False,
            refresh_jti="rjti-123",
        )
        payload = verify_access(token)
        assert payload["sub"] == "u1"
        assert payload["project_id"] == "p1"
        assert payload["rjti"] == "rjti-123"
        assert payload["jti"] == jti
        assert payload["exp"] == exp

    def test_refresh_roundtrip(self):
        from app.services.jwt_service import sign_refresh, verify_refresh

        token, jti, exp = sign_refresh("u1")
        payload = verify_refresh(token)
        assert payload["sub"] == "u1"
        assert payload["jti"] == jti
        assert payload["type"] == "refresh"

    def test_verify_access_expired(self, monkeypatch):
        import jwt

        from app.services.jwt_service import sign_access, verify_access

        token, _, _ = sign_access("u1", "alice", "p1", "proj", [], False, "rjti")
        # 만료 강제: exp를 과거로 덮어쓰기
        payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        payload["exp"] = int(time.time()) - 10
        tampered = jwt.encode(payload, "test-secret-key-for-jwt-tests", algorithm="HS256")
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_access(tampered)

    def test_verify_refresh_wrong_type(self):
        import jwt

        from app.services.jwt_service import sign_access, verify_refresh

        # access 토큰을 refresh 경로로 검증하면 실패
        token, _, _ = sign_access("u1", "alice", "p1", "proj", [], False, "rjti")
        with pytest.raises(jwt.InvalidTokenError):
            verify_refresh(token)


# ──────────────────────────────────────────────────────────────────
# session_store 단위 테스트
# ──────────────────────────────────────────────────────────────────

class TestSessionStore:
    @pytest.mark.asyncio
    async def test_store_and_get(self):
        from app.services.session_store import get_session, store_session

        exp = int(time.time()) + 600
        await store_session("jti-abc", "ks-tok", "proj-1", "user-1", exp)
        sess = await get_session("jti-abc")
        assert sess is not None
        assert sess["keystone_token"] == "ks-tok"
        assert sess["project_id"] == "proj-1"

    @pytest.mark.asyncio
    async def test_delete_session(self):
        from app.services.session_store import delete_session, get_session, store_session

        exp = int(time.time()) + 600
        await store_session("jti-del", "ks-tok", "proj-1", "user-1", exp)
        await delete_session("jti-del")
        assert await get_session("jti-del") is None

    @pytest.mark.asyncio
    async def test_missing_returns_none(self):
        from app.services.session_store import get_session

        assert await get_session("nonexistent-jti") is None


# ──────────────────────────────────────────────────────────────────
# HTTP 엔드포인트 통합 테스트
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def _ks_authenticate():
    with patch("app.api.identity.auth.keystone.authenticate", return_value=dict(_KS_DATA)) as m:
        yield m


@pytest.fixture
def _ks_get_user():
    user_mock = MagicMock()
    user_mock.default_project_id = ""
    conn_mock = MagicMock()
    conn_mock.identity.get_user.return_value = user_mock
    with patch("app.api.identity.auth.keystone.get_openstack_connection", return_value=conn_mock):
        yield conn_mock


@pytest.fixture
def _ks_validate_ok():
    with patch(
        "app.api.identity.auth.keystone.validate_token",
        return_value=dict(_KS_DATA),
    ) as m:
        yield m


@pytest.fixture
def _rate_limiter_off():
    with patch("app.rate_limit.limiter.limit", return_value=lambda f: f):
        yield


@pytest.mark.asyncio
async def test_login_returns_access_and_refresh(
    _ks_authenticate, _ks_get_user, _rate_limiter_off
):
    """로그인 응답에 token(access JWT)과 refresh_token이 모두 포함되어야 한다."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": "alice", "password": "pw", "project_name": "myproject"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["refresh_token"]
    assert body["expires_at"]
    # token은 JWT 형식 (점 3개)
    assert body["token"].count(".") == 2
    assert body["refresh_token"].count(".") == 2


@pytest.mark.asyncio
async def test_bearer_access_protects_me_endpoint(
    _ks_authenticate, _ks_get_user, _rate_limiter_off
):
    """Bearer access JWT로 /me 엔드포인트에 접근 가능해야 한다."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "alice", "password": "pw", "project_name": "myproject"},
        )
        access = login.json()["token"]
        me = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_legacy_x_auth_token_still_works(_rate_limiter_off):
    """X-Auth-Token 레거시 헤더로 /me가 동작해야 한다 (하위호환)."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    with patch(
        "app.api.deps._cached_validate",
        new=AsyncMock(return_value=dict(_KS_DATA)),
    ), patch(
        "app.api.deps._check_session_timeout",
        new=AsyncMock(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            me = await ac.get(
                "/api/auth/me",
                headers={"X-Auth-Token": _KEYSTONE_TOKEN, "X-Project-Id": "proj-1"},
            )
    assert me.status_code == 200
    assert me.json()["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_expired_access_jwt_returns_401(_rate_limiter_off):
    """만료된 access JWT로 요청 시 401을 반환해야 한다."""
    import jwt as pyjwt

    from httpx import ASGITransport, AsyncClient

    from app.main import app

    payload = {
        "sub": "user-1",
        "jti": "test-jti",
        "rjti": "rjti-x",
        "exp": int(time.time()) - 10,
        "iat": int(time.time()) - 920,
        "username": "alice",
        "project_id": "proj-1",
        "project_name": "myproject",
        "roles": ["member"],
        "is_system_admin": False,
    }
    expired_token = pyjwt.encode(payload, "test-secret-key-for-jwt-tests", algorithm="HS256")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(
    _ks_authenticate, _ks_get_user, _ks_validate_ok, _rate_limiter_off
):
    """refresh 호출 시 새 토큰 쌍이 발급되고, 기존 refresh로 재호출 시 401."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "alice", "password": "pw", "project_name": "myproject"},
        )
        old_refresh = login.json()["refresh_token"]
        old_access = login.json()["token"]

        # 첫 refresh → 성공
        r1 = await ac.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r1.status_code == 200
        new_access = r1.json()["token"]
        new_refresh = r1.json()["refresh_token"]
        assert new_access != old_access
        assert new_refresh != old_refresh

        # 같은 refresh 재사용 → 401 (토큰 회전)
        r2 = await ac.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_session(
    _ks_authenticate, _ks_get_user, _rate_limiter_off
):
    """로그아웃 후 refresh 토큰으로 갱신 시도 시 401을 반환해야 한다."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    with patch("app.api.identity.auth.keystone.revoke_token"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login = await ac.post(
                "/api/auth/login",
                json={"username": "alice", "password": "pw", "project_name": "myproject"},
            )
            access = login.json()["token"]
            refresh = login.json()["refresh_token"]

            logout = await ac.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {access}"},
            )
            assert logout.status_code == 200

            # 로그아웃 후 refresh 사용 → 401
            r = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
            assert r.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_header_returns_401(_rate_limiter_off):
    """인증 헤더 없이 protected 엔드포인트 접근 시 401."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me")
    assert resp.status_code == 401
