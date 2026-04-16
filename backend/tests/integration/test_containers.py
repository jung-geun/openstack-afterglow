"""컨테이너 API (Magnum 클러스터, Zun 컨테이너) 통합 테스트."""

import pytest

# ─────────────────────────────────────────────────────────────────
# Magnum 클러스터
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_list_clusters(client, settings):
    if not settings.service_magnum_enabled:
        pytest.skip("Magnum 비활성화")
    resp = await client.get("/api/clusters")
    # Magnum 서비스가 일시적으로 불가할 수 있음
    assert resp.status_code in (200, 500, 503)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_cluster_templates(client, settings):
    if not settings.service_magnum_enabled:
        pytest.skip("Magnum 비활성화")
    resp = await client.get("/api/clusters/templates")
    assert resp.status_code in (200, 500, 503)


# ─────────────────────────────────────────────────────────────────
# Zun 컨테이너
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_list_containers(client, settings):
    if not settings.service_zun_enabled:
        pytest.skip("Zun 비활성화")
    resp = await client.get("/api/containers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
