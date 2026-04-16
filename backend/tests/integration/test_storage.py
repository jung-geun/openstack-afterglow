"""스토리지 API (볼륨, 백업, 스냅샷, 파일 스토리지) 통합 테스트."""
import asyncio
import pytest


# ─────────────────────────────────────────────────────────────────
# 볼륨
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_volumes(client):
    resp = await client.get("/api/volumes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_volume_crud(client):
    """볼륨 생성 → 상세 조회 → 삭제."""
    # 생성
    resp = await client.post("/api/volumes", json={
        "name": "union-test-vol-integration",
        "size_gb": 1,
    })
    assert resp.status_code in (200, 201)
    vol = resp.json()
    vol_id = vol["id"]
    assert vol["name"] == "union-test-vol-integration"

    # available 대기 (최대 60초)
    for _ in range(12):
        await asyncio.sleep(5)
        detail = (await client.get(f"/api/volumes/{vol_id}")).json()
        if detail["status"] == "available":
            break
    else:
        pytest.fail("볼륨이 available 상태가 되지 않음")

    # 상세 조회
    resp = await client.get(f"/api/volumes/{vol_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == vol_id

    # 삭제
    resp = await client.delete(f"/api/volumes/{vol_id}")
    assert resp.status_code == 204


# ─────────────────────────────────────────────────────────────────
# 볼륨 백업
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_volume_backups(client):
    resp = await client.get("/api/volumes/backups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 볼륨 스냅샷
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_volume_snapshots(client):
    resp = await client.get("/api/volume-snapshots")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# 파일 스토리지 (Manila)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_file_storages(client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await client.get("/api/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_file_storage_quota(client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await client.get("/api/file-storage/quota")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # 응답이 중첩 구조 (gigabytes, shares 등) 또는 flat 구조일 수 있음
    assert len(data) > 0


@pytest.mark.asyncio(loop_scope="session")
async def test_list_share_types(client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await client.get("/api/file-storage/types")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# PR4: 일반 유저도 프로젝트 스코프 스토리지 리소스 조회 가능 확인
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_volumes_as_user(user_client):
    resp = await user_client.get("/api/volumes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_volume_backups_as_user(user_client):
    resp = await user_client.get("/api/volumes/backups")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_volume_snapshots_as_user(user_client):
    resp = await user_client.get("/api/volume-snapshots")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_file_storages_as_user(user_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await user_client.get("/api/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
