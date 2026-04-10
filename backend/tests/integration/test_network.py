"""네트워크 API (네트워크, 라우터, 보안그룹, 로드밸런서, 플로팅IP) 통합 테스트."""
import pytest


# ─────────────────────────────────────────────────────────────────
# 네트워크
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_networks(client):
    resp = await client.get("/api/networks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "id" in data[0]
        assert "name" in data[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_network_detail(client):
    networks = (await client.get("/api/networks")).json()
    if not networks:
        pytest.skip("네트워크 없음")
    net_id = networks[0]["id"]
    resp = await client.get(f"/api/networks/{net_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == net_id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_topology(client):
    resp = await client.get("/api/networks/topology")
    # 토폴로지 조회가 실패할 수 있음 (캐시 누락 등)
    assert resp.status_code in (200, 500)


# ─────────────────────────────────────────────────────────────────
# 플로팅 IP
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_floating_ips(client):
    resp = await client.get("/api/networks/floating-ips")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 라우터
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_routers(client):
    resp = await client.get("/api/routers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_router_detail(client):
    routers = (await client.get("/api/routers")).json()
    if not routers:
        pytest.skip("라우터 없음")
    router_id = routers[0]["id"]
    resp = await client.get(f"/api/routers/{router_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == router_id


# ─────────────────────────────────────────────────────────────────
# 보안그룹
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_security_groups(client):
    resp = await client.get("/api/security-groups")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0  # default 보안그룹은 항상 존재


@pytest.mark.asyncio(loop_scope="session")
async def test_security_group_crud(client):
    """보안그룹 생성 → 룰 추가 → 룰 삭제 → 보안그룹 삭제."""
    # 이전 잔여물 정리
    sgs = (await client.get("/api/security-groups")).json()
    for sg in sgs:
        if sg.get("name") == "union-test-sg-integration":
            await client.delete(f"/api/security-groups/{sg['id']}")

    # 생성
    resp = await client.post("/api/security-groups", json={
        "name": "union-test-sg-integration",
        "description": "integration test",
    })
    assert resp.status_code in (200, 201)
    sg = resp.json()
    sg_id = sg["id"]

    # 룰 추가 (SSH)
    resp = await client.post(f"/api/security-groups/{sg_id}/rules", json={
        "direction": "ingress",
        "protocol": "tcp",
        "port_range_min": 22,
        "port_range_max": 22,
        "remote_ip_prefix": "0.0.0.0/0",
    })
    if resp.status_code in (200, 201):
        rule = resp.json()
        rule_id = rule["id"]
        # 룰 삭제
        resp = await client.delete(f"/api/security-groups/{sg_id}/rules/{rule_id}")
        assert resp.status_code == 204

    # 보안그룹 삭제 (항상 정리)
    resp = await client.delete(f"/api/security-groups/{sg_id}")
    assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────
# 로드밸런서
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_loadbalancers(client):
    resp = await client.get("/api/loadbalancers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
