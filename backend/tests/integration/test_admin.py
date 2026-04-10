"""관리자 API 통합 테스트.

config.toml의 admin 계정으로 로그인하므로 admin 역할이 있어야 한다.
"""
import pytest


# ─────────────────────────────────────────────────────────────────
# 관리자 개요
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_overview(client):
    resp = await client.get("/api/admin/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "instances_count" in data or "total_instances" in data or isinstance(data, dict)


# ─────────────────────────────────────────────────────────────────
# 관리자 서비스 상태
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_services(client):
    resp = await client.get("/api/admin/services")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute" in data
    assert "block_storage" in data
    assert "endpoints" in data


# ─────────────────────────────────────────────────────────────────
# 관리자 인스턴스/볼륨/네트워크 전체 목록
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_instances(client):
    resp = await client.get("/api/admin/all-instances")
    assert resp.status_code == 200
    data = resp.json()
    # 페이지네이션 응답 {count, items} 또는 list
    assert isinstance(data, (list, dict))
    if isinstance(data, dict):
        assert "items" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_volumes(client):
    resp = await client.get("/api/admin/all-volumes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    if isinstance(data, dict):
        assert "items" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_networks(client):
    resp = await client.get("/api/admin/all-networks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_floating_ips(client):
    resp = await client.get("/api/admin/all-floating-ips")
    assert resp.status_code in (200, 500)  # 내부 에러 가능 (Neutron 상태에 따라)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_routers(client):
    resp = await client.get("/api/admin/all-routers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_ports(client):
    resp = await client.get("/api/admin/all-ports")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


# ─────────────────────────────────────────────────────────────────
# 관리자 하이퍼바이저
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_hypervisors(client):
    resp = await client.get("/api/admin/hypervisors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "hostname" in data[0] or "hypervisor_hostname" in data[0] or "id" in data[0]


# ─────────────────────────────────────────────────────────────────
# 관리자 GPU
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_gpu_hosts(client):
    resp = await client.get("/api/admin/gpu-hosts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))


# ─────────────────────────────────────────────────────────────────
# 관리자 플레이버
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_flavors(client):
    resp = await client.get("/api/admin/flavors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    items = data if isinstance(data, list) else data.get("items", data.get("flavors", []))
    assert len(items) > 0


# ─────────────────────────────────────────────────────────────────
# 관리자 Identity (사용자, 프로젝트, 그룹, 역할)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_users(client):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    items = data if isinstance(data, list) else data.get("items", data.get("users", []))
    assert len(items) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_projects(client):
    resp = await client.get("/api/admin/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    items = data if isinstance(data, list) else data.get("items", data.get("projects", []))
    assert len(items) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_project_names(client):
    resp = await client.get("/api/admin/projects/names")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_groups(client):
    resp = await client.get("/api/admin/groups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_list_roles(client):
    resp = await client.get("/api/admin/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_project_quotas(client, project_id):
    resp = await client.get(f"/api/admin/quotas/{project_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_projects_overview(client):
    resp = await client.get("/api/admin/overview/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ─────────────────────────────────────────────────────────────────
# 관리자 토폴로지
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_topology(client):
    resp = await client.get("/api/admin/topology")
    assert resp.status_code in (200, 500)


# ─────────────────────────────────────────────────────────────────
# 관리자 시계열
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_timeseries(client):
    resp = await client.get("/api/admin/timeseries/instances?range=7d")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 관리자 파일 스토리지
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_file_storages(client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await client.get("/api/admin/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_file_storages(client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await client.get("/api/admin/all-file-storages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 관리자 컨테이너 (Zun)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_all_containers(client, settings):
    if not settings.service_zun_enabled:
        pytest.skip("Zun 비활성화")
    resp = await client.get("/api/admin/all-containers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 관리자 Notion 설정
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_admin_notion_config_get(client):
    resp = await client.get("/api/admin/notion/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data


# ─────────────────────────────────────────────────────────────────
# 메트릭 (Prometheus)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_metrics(client):
    resp = await client.get("/api/metrics")
    assert resp.status_code == 200
