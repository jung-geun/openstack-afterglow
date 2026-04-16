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
    body = resp.json()
    assert isinstance(body, dict)
    # 회귀: v1 endpoint fallback 시 모든 키가 limit=-1 (실패 fallback) 이면 안 됨.
    # 실제 quota dict 구조 확인 — v2 endpoint 가 정상 응답해야 "shares" 키 등이 존재.
    for key in ("shares", "gigabytes", "share_networks"):
        assert key in body, f"quota 응답에 '{key}' 키 없음 (Manila v1 endpoint fallback 의심)"
        assert "limit" in body[key], f"quota['{key}'] 에 'limit' 없음"


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
