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

import os
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings

# 환경변수는 루트 tests/conftest.py에서 설정됨
from app.main import app


@dataclass
class IntegrationResources:
    """통합 테스트용 OpenStack 리소스 식별자 + SSH 자격증명.

    환경변수 부재 시 픽스처 단계에서 pytest.skip으로 처리.
    """

    image_id: str
    flavor_small: str
    flavor_medium: str
    library_ids: list[str]
    ssh_key_path: str
    ssh_user: str
    ssh_key_name: str


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
# 전역 Redis 테스트 패치 비활성화 — 통합 테스트는 실제 Redis를 사용
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fake_redis_global():
    """tests/conftest.py의 전역 fakeredis autouse 픽스처를 여기서 no-op으로 오버라이드.

    통합 테스트는 실제 Keystone 로그인 후 세션을 실제 Redis에 저장하므로
    fakeredis로 교체하면 이후 요청에서 세션을 찾지 못해 401이 발생한다.
    """
    yield


@pytest.fixture(autouse=True)
async def _flush_afterglow_cache():
    """루트 Redis flush를 통합 테스트에서 비활성화한다.

    루트 tests/conftest.py의 _flush_afterglow_cache는 단위 테스트 격리를 위해
    afterglow:* 전체를 지우는데, 통합 테스트에서는 실제 Redis의
    afterglow:refresh:* 세션 키까지 테스트 사이에 삭제해 인증이 401로 깨진다.
    """
    yield


# ---------------------------------------------------------------------------
# 설정 / 크리덴셜
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def integration_resources():
    """실 인프라 통합 테스트용 image/flavor/SSH 자격증명.

    누락 시 자동 skip — slow 마커가 붙은 테스트에서만 사용된다.
    """
    image_id = os.environ.get("AFTERGLOW_TEST_IMAGE_ID", "").strip()
    flavor_small = os.environ.get("AFTERGLOW_TEST_FLAVOR_SMALL", "").strip()
    flavor_medium = os.environ.get("AFTERGLOW_TEST_FLAVOR_MEDIUM", "").strip()
    ssh_key_path = os.environ.get("AFTERGLOW_TEST_SSH_KEY", "").strip()

    missing = [
        name
        for name, val in [
            ("AFTERGLOW_TEST_IMAGE_ID", image_id),
            ("AFTERGLOW_TEST_FLAVOR_SMALL", flavor_small),
            ("AFTERGLOW_TEST_FLAVOR_MEDIUM", flavor_medium),
            ("AFTERGLOW_TEST_SSH_KEY", ssh_key_path),
        ]
        if not val
    ]
    if missing:
        pytest.skip(f"통합 테스트 환경변수 미설정: {', '.join(missing)}")

    if not os.path.isfile(ssh_key_path):
        pytest.skip(f"SSH 키 파일이 존재하지 않음: {ssh_key_path}")

    # OpenSSH는 키 모드가 0o600(또는 더 제한적)이 아니면 거부 — CI에서 자동 보정.
    try:
        os.chmod(ssh_key_path, 0o600)
    except OSError:
        pass

    library_ids_raw = os.environ.get("AFTERGLOW_TEST_LIBRARY_IDS", "python311").strip()
    library_ids = [s.strip() for s in library_ids_raw.split(",") if s.strip()]
    ssh_user = os.environ.get("AFTERGLOW_TEST_SSH_USER", "ubuntu").strip() or "ubuntu"
    ssh_key_name = os.environ.get("AFTERGLOW_TEST_SSH_KEY_NAME", "afterglow-e2e-test").strip()

    return IntegrationResources(
        image_id=image_id,
        flavor_small=flavor_small,
        flavor_medium=flavor_medium,
        library_ids=library_ids,
        ssh_key_path=ssh_key_path,
        ssh_user=ssh_user,
        ssh_key_name=ssh_key_name,
    )


@pytest.fixture(scope="session", autouse=True)
async def flush_cache_before_integration():
    """통합 테스트 세션 시작 전 Redis 캐시를 초기화한다.

    단위 테스트가 먼저 실행될 경우(npm run test:all), mock conn이 빈 결과를
    Redis에 캐시해 통합 테스트에서 캐시 히트로 잘못된 값을 받는 문제를 방지한다.
    Redis 미실행 시 조용히 무시.
    """
    try:
        from app.services.cache import _get_client

        client = _get_client()
        # afterglow:admin:* 키 전체 삭제 (관리자 API 캐시)
        keys = await client.keys("afterglow:admin:*")
        if keys:
            await client.delete(*keys)
    except Exception:
        pass
    yield


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


@pytest.fixture(scope="session")
def project_b_credentials_fx():
    """두 번째 프로젝트 크리덴셜 (격리 테스트용). 미설정 시 skip."""
    from .credentials import project_b_credentials

    creds = project_b_credentials()
    if creds is None:
        pytest.skip(
            "project_b 크리덴셜 미설정 — "
            "AFTERGLOW_TEST_PROJECT_B_USERNAME / AFTERGLOW_TEST_PROJECT_B_PASSWORD / "
            "AFTERGLOW_TEST_PROJECT_B_NAME 환경변수를 설정하세요."
        )
    return creds


# 하위 호환: 기존 테스트가 사용하던 `credentials` 픽스처는 admin 계정을 반환
@pytest.fixture(scope="session")
def credentials(admin_credentials_fx):
    """기존 호환성 유지: admin 크리덴셜 반환."""
    return admin_credentials_fx


@pytest.fixture(scope="session")
async def project_b_auth_data(project_b_credentials_fx):
    """project_b 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/v1/auth/login", json=project_b_credentials_fx)
        assert resp.status_code == 200, f"project_b 로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
async def project_b_client(project_b_auth_data):
    """project_b 계정으로 인증된 AsyncClient (격리 테스트용)."""
    headers = {
        "Authorization": f"Bearer {project_b_auth_data['token']}",
        "X-Project-Id": project_b_auth_data["project_id"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers,
        timeout=30,
    ) as ac:
        yield ac


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
        resp = await ac.post("/api/v1/auth/login", json=admin_credentials_fx)
        assert resp.status_code == 200, f"admin 로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
async def admin_user_auth_data(admin_user_credentials_fx):
    """admin_user 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/v1/auth/login", json=admin_user_credentials_fx)
        assert resp.status_code == 200, f"admin_user 로그인 실패: {resp.text}"
        return resp.json()


@pytest.fixture(scope="session")
async def user_auth_data(user_credentials_fx):
    """일반 유저 계정으로 실제 Keystone 로그인. 세션 전체에서 재사용."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        resp = await ac.post("/api/v1/auth/login", json=user_credentials_fx)
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
    """인증 헤더 dict (admin 계정).

    get_token_info는 Authorization: Bearer JWT 경로만 지원한다.
    """
    return {
        "Authorization": f"Bearer {token}",
        "X-Project-Id": project_id,
    }


# ---------------------------------------------------------------------------
# HTTP 클라이언트
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def admin_client(admin_auth_data):
    """admin 계정으로 인증된 AsyncClient."""
    headers = {
        "Authorization": f"Bearer {admin_auth_data['token']}",
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
        "Authorization": f"Bearer {admin_user_auth_data['token']}",
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
        "Authorization": f"Bearer {user_auth_data['token']}",
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
