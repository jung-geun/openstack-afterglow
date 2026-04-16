"""파일 스토리지 (Manila) 통합 테스트 — manila 활성화 시만 실행."""
import pytest


# ─────────────────────────────────────────────────────────────────
# 파일 스토리지 목록 (admin 계정)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_file_storages_admin(admin_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await admin_client.get("/api/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_file_storage_quota_admin(admin_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await admin_client.get("/api/file-storage/quota")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_share_types_admin(admin_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await admin_client.get("/api/file-storage/types")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_share_networks_admin(admin_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await admin_client.get("/api/share-networks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_security_services_admin(admin_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await admin_client.get("/api/security-services")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ─────────────────────────────────────────────────────────────────
# PR4: 일반 유저도 파일 스토리지 조회 가능 확인
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio(loop_scope="session")
async def test_list_file_storages_user(user_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await user_client.get("/api/file-storage")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_share_networks_user(user_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await user_client.get("/api/share-networks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_security_services_user(user_client, settings):
    if not settings.service_manila_enabled:
        pytest.skip("Manila 비활성화")
    resp = await user_client.get("/api/security-services")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
