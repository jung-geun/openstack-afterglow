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
async def test_dynamic_share_not_visible_cross_project(admin_client, admin_auth_data, project_b_client):
    """A 프로젝트가 생성한 dynamic share는 B 프로젝트 user의 list에서 미노출."""
    require_service("service_manila_enabled")

    admin_pid = admin_auth_data["project_id"]
    share_id = None
    try:
        resp = await admin_client.post(
            "/api/v1/file-storage",
            json={
                "name": "test-isolation-dynamic",
                "size_gb": 1,
                "metadata": {"union_project_id": admin_pid},
            },
        )
        assert resp.status_code == 201, f"share 생성 실패: {resp.text}"
        share_id = resp.json()["id"]

        # project B → A의 private dynamic share가 목록에 없어야 함
        resp_b = await project_b_client.get("/api/v1/file-storage?refresh=true")
        assert resp_b.status_code == 200
        ids_b = {s["id"] for s in resp_b.json()}
        assert share_id not in ids_b, "다른 프로젝트의 private dynamic share가 project_b에 노출됨"
    finally:
        if share_id:
            await admin_client.delete(f"/api/v1/file-storage/{share_id}")


@pytest.mark.asyncio
async def test_public_prebuilt_share_visible_cross_project(admin_client, project_b_client, settings):
    """is_public=True인 prebuilt share는 B 프로젝트 user의 list에서 노출."""
    require_service("service_manila_enabled")

    # 기존 public share를 검색 (prebuilt 라이브러리 빌드 완료 후 set_share_public=True된 share)
    resp = await admin_client.get("/api/v1/file-storage?refresh=true")
    assert resp.status_code == 200

    public_shares = [s for s in resp.json() if s.get("is_public")]
    if not public_shares:
        pytest.skip("공개 share 없음 — prebuilt 라이브러리 빌드 완료 후 재실행")

    public_id = public_shares[0]["id"]

    # project B도 public share를 볼 수 있어야 함
    resp_b = await project_b_client.get("/api/v1/file-storage?refresh=true")
    assert resp_b.status_code == 200
    ids_b = {s["id"] for s in resp_b.json()}
    assert public_id in ids_b, f"public share {public_id}가 project_b 목록에 미노출"


@pytest.mark.asyncio
async def test_direct_get_cross_project_share_returns_404(admin_client, admin_auth_data, project_b_client):
    """B 프로젝트가 A 프로젝트의 private dynamic share ID를 직접 GET → 404."""
    require_service("service_manila_enabled")

    admin_pid = admin_auth_data["project_id"]
    share_id = None
    try:
        resp = await admin_client.post(
            "/api/v1/file-storage",
            json={
                "name": "test-isolation-404",
                "size_gb": 1,
                "metadata": {"union_project_id": admin_pid},
            },
        )
        assert resp.status_code == 201, f"share 생성 실패: {resp.text}"
        share_id = resp.json()["id"]

        # project B가 A의 private share를 직접 GET → 404
        resp_b = await project_b_client.get(f"/api/v1/file-storage/{share_id}")
        assert resp_b.status_code == 404, f"격리 실패: project_b가 private share를 조회함 (status={resp_b.status_code})"
    finally:
        if share_id:
            await admin_client.delete(f"/api/v1/file-storage/{share_id}")
