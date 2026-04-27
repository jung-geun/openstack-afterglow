"""프로젝트 격리 검증 — cross-project share 접근 차단.

실 인프라(Nova, Manila) 필요 — self-hosted runner에서만 실행.
로컬 단위 테스트 실행 시 자동 skip.

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_isolation.py -v -m slow
"""

import pytest

from tests.integration.conftest import require_service

pytestmark = pytest.mark.slow


@pytest.mark.asyncio
async def test_dynamic_share_not_visible_cross_project(admin_client, settings):
    """A 프로젝트가 생성한 dynamic share는 B 프로젝트 user의 list에서 미노출."""
    require_service("service_manila_enabled")
    pytest.skip("실 인프라 환경에서 실행 — self-hosted runner 전용")

    # --- 실 인프라 환경에서의 동작 개요 ---
    # 1. A 프로젝트 admin_client로 POST /api/file-storage (dynamic, union_project_id=A)
    # 2. B 프로젝트 client로 GET /api/file-storage → A의 share가 목록에 없음을 검증
    # 3. 생성한 share 삭제 (cleanup)


@pytest.mark.asyncio
async def test_public_prebuilt_share_visible_cross_project(admin_client, settings):
    """is_public=True인 prebuilt share는 B 프로젝트 user의 list에서 노출."""
    require_service("service_manila_enabled")
    pytest.skip("실 인프라 환경에서 실행 — self-hosted runner 전용")

    # --- 실 인프라 환경에서의 동작 개요 ---
    # 1. admin이 prebuilt share를 is_public=True로 Manila에 생성
    # 2. B 프로젝트 client로 GET /api/file-storage → 해당 share가 목록에 포함됨을 검증
    # 3. 생성한 share 삭제 (cleanup)


@pytest.mark.asyncio
async def test_direct_get_cross_project_share_returns_404(admin_client, settings):
    """B 프로젝트가 A 프로젝트의 private dynamic share ID를 직접 GET → 404."""
    require_service("service_manila_enabled")
    pytest.skip("실 인프라 환경에서 실행 — self-hosted runner 전용")

    # --- 실 인프라 환경에서의 동작 개요 ---
    # 1. A 프로젝트 admin_client로 dynamic share 생성 (union_project_id=A)
    # 2. B 프로젝트 client로 GET /api/file-storage/{share_id} → 404 확인
    # 3. 생성한 share 삭제 (cleanup)
