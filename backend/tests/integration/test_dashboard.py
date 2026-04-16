"""대시보드, 메트릭, 라이브러리, 사이트 설정, 유저 대시보드 통합 테스트."""

import pytest

# ─────────────────────────────────────────────────────────────────
# 대시보드
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_summary(client):
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "instances" in data
    assert "compute" in data
    assert "storage" in data
    assert "gpu_used" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_config(client):
    resp = await client.get("/api/dashboard/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "refresh_interval_ms" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_quotas(client):
    resp = await client.get("/api/dashboard/quotas")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute" in data
    assert "storage" in data
    assert "network" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_usage(client):
    resp = await client.get("/api/dashboard/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "start" in data
    assert "end" in data


# ─────────────────────────────────────────────────────────────────
# 사이트 설정 (인증 불필요)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_site_config(anon_client):
    resp = await anon_client.get("/api/site-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "site_name" in data
    assert "services" in data


# ─────────────────────────────────────────────────────────────────
# 헬스체크 (인증 불필요)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_health(anon_client):
    resp = await anon_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────
# 라이브러리
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_list_libraries(client):
    resp = await client.get("/api/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_list_prebuilt_file_storages(client):
    resp = await client.get("/api/libraries/file-storages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 유저 대시보드
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_user_dashboard_summary(client):
    resp = await client.get("/api/user-dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


# ─────────────────────────────────────────────────────────────────
# 프로필
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_get_profile(client):
    resp = await client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data or "id" in data


# ─────────────────────────────────────────────────────────────────
# PR4: 일반 유저도 대시보드/프로필 조회 가능 확인
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_summary_as_user(user_client):
    resp = await user_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "instances" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_quotas_as_user(user_client):
    resp = await user_client.get("/api/dashboard/quotas")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_user_dashboard_summary_as_user(user_client):
    resp = await user_client.get("/api/user-dashboard/summary")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_profile_as_user(user_client):
    resp = await user_client.get("/api/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data or "id" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_config_public(anon_client):
    """dashboard/config는 인증 없이도 접근 가능해야 한다."""
    resp = await anon_client.get("/api/dashboard/config")
    assert resp.status_code == 200
    assert "refresh_interval_ms" in resp.json()
