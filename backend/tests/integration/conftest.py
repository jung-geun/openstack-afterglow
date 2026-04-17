"""
통합 테스트 공통 픽스처.

config.toml 또는 credentials.toml 의 실제 OpenStack 인증 정보를 사용하여 로그인 후
토큰을 획득하고, httpx AsyncClient로 FastAPI 앱에 실제 요청을 보낸다.

사전 조건:
  - Redis 실행 중 (config.toml의 redis_url)
  - OpenStack 접근 가능 (config.toml의 openstack 섹션 또는 credentials.toml)
  - 환경변수 AFTERGLOW_ALLOW_INSECURE=1 (개발 시크릿 키 허용)

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/ -v

admin/user 권한 분리 테스트를 위한 일반 유저 계정 설정:
  cp tests/integration/credentials.toml.example tests/integration/credentials.toml
  # 파일을 열어 [user] 섹션 비밀번호 기입
  또는 환경변수: AFTERGLOW_TEST_USER_USERNAME, AFTERGLOW_TEST_USER_PASSWORD, AFTERGLOW_TEST_USER_PROJECT
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings

# 환경변수는 루트 tests/conftest.py에서 설정됨
from app.main import app

# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------


def assert_forbidden(resp) -> None:
    """403 응답 + 관리자 관련 메시지 검증."""
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "detail" in body


def require_service(flag: str) -> None:
    """선택적 서비스 비활성화 시 테스트 skip.

    사용 예:
        require_service("service_manila_enabled")
    """
    settings = get_settings()
    if not getattr(settings, flag, False):
        pytest.skip(f"{flag}=false — 서비스 미활성화")


# ---------------------------------------------------------------------------
# 설정 / 크리덴셜
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def admin_credentials_fx():
    """admin 크리덴셜 (credentials.toml > config.toml 폴백)."""
    from .credentials import admin_credentials

    return admin_credentials()


@pytest.fixture(scope="session")
def admin_user_credentials_fx():
    """admin_user 크리덴셜 (admin 프로젝트 admin role 보유, default_project ≠ admin 가능). 미설정 시 skip."""
    from .credentials import admin_user_credentials

    creds = admin_user_credentials()
    if creds is None:
        pytest.skip(
            "admin_user 크리덴셜 미설정 — "
            "tests/integration/credentials.toml 의 [admin_user] 섹션 또는 "
            "AFTERGLOW_TEST_ADMIN_USER_USERNAME / AFTERGLOW_TEST_ADMIN_USER_PASSWORD 환경변수를 설정하세요."
        )
    return creds


@pytest.fixture(scope="session")
def user_credentials_fx():
    """일반 유저 크리덴셜. 미설정 시 테스트 skip."""
    from .credentials import user_credentials

    creds = user_credentials()
    if creds is None:
        pytest.skip(
            "일반 유저 크리덴셜 미설정 — "
            "tests/integration/credentials.toml 의 [user] 섹션 또는 "
            "AFTERGLOW_TEST_USER_USERNAME / AFTERGLOW_TEST_USER_PASSWORD 환경변수를 설정하세요."
        )
    return creds


# 하위 호환: 기존 테스트가 사용하던 `credentials` 픽스처는 admin 계정을 반환
@pytest.fixture(scope="session")
def credentials(admin_credentials_fx):
    """기존 호환성 유지: admin 크리덴셜 반환."""
    return admin_credentials_fx


# ---------------------------------------------------------------------------
# 인증 데이터 (로그인)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def admin_auth_data(admin_credentials_fx):
    """admin 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/auth/login", json=admin_credentials_fx)
        assert resp.status_code == 200, f"admin 로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
async def admin_user_auth_data(admin_user_credentials_fx):
    """admin_user 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/auth/login", json=admin_user_credentials_fx)
        assert resp.status_code == 200, f"admin_user 로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
async def user_auth_data(user_credentials_fx):
    """일반 유저 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/auth/login", json=user_credentials_fx)
        assert resp.status_code == 200, f"일반 유저 로그인 실패: {resp.text}"
        return resp.json()


# 하위 호환: 기존 `auth_data` → admin 위임
@pytest.fixture(scope="session")
async def auth_data(admin_auth_data):
    return admin_auth_data


@pytest.fixture(scope="session")
def token(admin_auth_data):
    return admin_auth_data["token"]


@pytest.fixture(scope="session")
def project_id(admin_auth_data):
    return admin_auth_data["project_id"]


@pytest.fixture(scope="session")
def auth_headers(token, project_id):
    """인증 헤더 dict (admin 계정)."""
    return {
        "X-Auth-Token": token,
        "X-Project-Id": project_id,
    }


# ---------------------------------------------------------------------------
# HTTP 클라이언트
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def admin_client(admin_auth_data):
    """admin 계정으로 인증된 AsyncClient."""
    headers = {
        "X-Auth-Token": admin_auth_data["token"],
        "X-Project-Id": admin_auth_data["project_id"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
        timeout=30,
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def admin_user_client(admin_user_auth_data):
    """admin_user 계정으로 인증된 AsyncClient (scoped project ≠ admin 일 수 있는 admin 권한 검증용)."""
    headers = {
        "X-Auth-Token": admin_user_auth_data["token"],
        "X-Project-Id": admin_user_auth_data["project_id"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
        timeout=30,
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def user_client(user_auth_data):
    """일반 유저 계정으로 인증된 AsyncClient (권한 분리 테스트용)."""
    headers = {
        "X-Auth-Token": user_auth_data["token"],
        "X-Project-Id": user_auth_data["project_id"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
        timeout=30,
    ) as ac:
        yield ac


# 하위 호환: 기존 `client` → admin_client 위임
@pytest.fixture(scope="session")
async def client(auth_headers):
    """인증 헤더가 포함된 AsyncClient (admin). 기존 테스트 하위 호환용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers,
        timeout=30,
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def anon_client():
    """인증 없는 AsyncClient (공개 엔드포인트 테스트용)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30,
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# 세션 teardown — Redis 캐시 정리
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
async def _flush_cache_after_session():
    """세션 종료 시 afterglow:cache:* 키 일괄 삭제.

    쓰기 테스트가 생성한 리소스의 캐시 잔여물을 제거한다.
    세션 키(afterglow:session:*)는 TTL로 자연 만료되므로 건드리지 않는다.
    Redis가 없으면 조용히 무시 (단위 테스트 환경 호환).
    """
    yield
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(get_settings().redis_url)
        async for key in r.scan_iter("afterglow:cache:*"):
            await r.delete(key)
        await r.aclose()
    except Exception:
        pass
