"""컴퓨트 API (인스턴스, 이미지, 키페어, 플레이버) 통합 테스트."""
import pytest


# ─────────────────────────────────────────────────────────────────
# 이미지
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_images(client):
    resp = await client.get("/api/images")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    img = data[0]
    assert "id" in img
    assert "name" in img
    assert "status" in img


@pytest.mark.asyncio(loop_scope="session")
async def test_get_image_detail(client):
    # 먼저 목록에서 ID 획득
    images = (await client.get("/api/images")).json()
    assert len(images) > 0
    image_id = images[0]["id"]

    resp = await client.get(f"/api/images/{image_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == image_id
    assert "checksum" in data
    assert "container_format" in data
    assert "properties" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_get_image_not_found(client):
    resp = await client.get("/api/images/nonexistent-id-12345")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────
# 플레이버
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_flavors(client):
    resp = await client.get("/api/flavors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    fl = data[0]
    assert "id" in fl
    assert "name" in fl
    assert "vcpus" in fl
    assert "ram" in fl


# ─────────────────────────────────────────────────────────────────
# 키페어
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_keypairs(client):
    resp = await client.get("/api/keypairs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_keypair_crud(client):
    """키페어 생성 → 목록 확인 → 삭제."""
    name = "union-test-keypair-integration"

    # 이전 잔여물 정리
    await client.delete(f"/api/keypairs/{name}")

    # 생성
    resp = await client.post("/api/keypairs", json={"name": name})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == name
    assert "public_key" in data

    # 목록에 포함 확인
    resp = await client.get("/api/keypairs")
    names = [kp["name"] for kp in resp.json()]
    assert name in names

    # 삭제
    resp = await client.delete(f"/api/keypairs/{name}")
    assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────
# 인스턴스
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_instances(client):
    resp = await client.get("/api/instances")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_instance_detail(client):
    """인스턴스가 있으면 상세 조회 테스트."""
    instances = (await client.get("/api/instances")).json()
    if not instances:
        pytest.skip("실행 중인 인스턴스 없음")

    instance_id = instances[0]["id"]
    resp = await client.get(f"/api/instances/{instance_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == instance_id
    assert "status" in data
    assert "ip_addresses" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_get_instance_interfaces(client):
    instances = (await client.get("/api/instances")).json()
    if not instances:
        pytest.skip("실행 중인 인스턴스 없음")

    instance_id = instances[0]["id"]
    resp = await client.get(f"/api/instances/{instance_id}/interfaces")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_instance_volumes(client):
    instances = (await client.get("/api/instances")).json()
    if not instances:
        pytest.skip("실행 중인 인스턴스 없음")

    instance_id = instances[0]["id"]
    resp = await client.get(f"/api/instances/{instance_id}/volumes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_instance_security_groups(client):
    instances = (await client.get("/api/instances")).json()
    if not instances:
        pytest.skip("실행 중인 인스턴스 없음")

    instance_id = instances[0]["id"]
    resp = await client.get(f"/api/instances/{instance_id}/security-groups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# PR4: 일반 유저도 프로젝트 스코프 리소스 조회 가능 확인
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_images_as_user(user_client):
    resp = await user_client.get("/api/images")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_flavors_as_user(user_client):
    resp = await user_client.get("/api/flavors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_keypairs_as_user(user_client):
    resp = await user_client.get("/api/keypairs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_instances_as_user(user_client):
    resp = await user_client.get("/api/instances")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
