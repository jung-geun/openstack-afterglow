"""k3s 클러스터 통합 테스트 — k3s 활성화 시만 실행."""

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_list_k3s_clusters_admin(admin_client, settings):
    if not getattr(settings, "service_k3s_enabled", False):
        pytest.skip("k3s 비활성화")
    resp = await admin_client.get("/api/k3s/clusters")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_k3s_clusters_user(user_client, settings):
    """일반 유저도 k3s 클러스터 목록을 조회할 수 있어야 한다."""
    if not getattr(settings, "service_k3s_enabled", False):
        pytest.skip("k3s 비활성화")
    resp = await user_client.get("/api/k3s/clusters")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
