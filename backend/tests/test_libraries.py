"""common/libraries.py 엔드포인트 + 서비스 단위 테스트."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_libraries_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/libraries")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_libraries_success(client, mock_conn):
    with patch("app.api.common.libraries.lib_svc") as mock_lib, patch("app.api.common.libraries.manila") as mock_manila:
        mock_lib.get_all.return_value = []
        mock_manila.list_file_storages.return_value = []
        resp = await client.get("/api/libraries")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_prebuilt_file_storages_unauthenticated():
    """인증 없이 접근 시 401 반환."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/libraries/file-storages")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_prebuilt_file_storages_success(client, mock_conn):
    with (
        patch("app.api.common.libraries.get_service_project_connection") as mock_svc_conn,
        patch("app.api.common.libraries.manila") as mock_manila,
    ):
        mock_svc_conn.return_value = mock_conn
        mock_manila.list_file_storages.return_value = []
        resp = await client.get("/api/libraries/file-storages")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ────── 라이브러리 검증 서비스 ──────


def test_validate_compatible_libraries():
    """python311 + torch + vllm 조합은 호환."""
    from app.services.libraries import validate_compatibility

    msgs = validate_compatibility(["python311", "torch", "vllm"])
    assert msgs == []


def test_validate_incompatible_ubuntu_version():
    """선택한 Ubuntu 버전을 지원하지 않는 라이브러리 경고."""
    from app.models.storage import LibraryConfig
    from app.services import libraries as lib_svc

    # ubuntu_versions=['22.04'] 라이브러리를 ubuntu 24.04와 함께 검증
    old_catalog = lib_svc._catalog[:]
    old_map = dict(lib_svc._catalog_by_id)
    try:
        restricted = LibraryConfig(
            id="restricted_lib",
            name="Restricted Lib",
            version="1.0",
            packages=[],
            ubuntu_versions=["22.04"],
        )
        lib_svc._catalog.append(restricted)
        lib_svc._catalog_by_id["restricted_lib"] = restricted

        msgs = lib_svc.validate_compatibility(["restricted_lib"], ubuntu_version="24.04")
        assert any("24.04" in m for m in msgs)
    finally:
        lib_svc._catalog[:] = old_catalog
        lib_svc._catalog_by_id.clear()
        lib_svc._catalog_by_id.update(old_map)


def test_validate_empty_selection():
    """빈 선택은 에러 없음."""
    from app.services.libraries import validate_compatibility

    msgs = validate_compatibility([])
    assert msgs == []


def test_check_python_version_conflict():
    """두 개의 Python 라이브러리 선택 시 충돌 감지."""
    from app.models.storage import LibraryConfig
    from app.services import libraries as lib_svc

    old_catalog = lib_svc._catalog[:]
    old_map = dict(lib_svc._catalog_by_id)
    try:
        py312 = LibraryConfig(
            id="python312",
            name="Python 3.12",
            version="3.12",
            packages=[],
        )
        lib_svc._catalog.append(py312)
        lib_svc._catalog_by_id["python312"] = py312

        conflict = lib_svc.check_python_version_conflict(["python311", "python312"])
        assert conflict is not None
        assert "충돌" in conflict
    finally:
        lib_svc._catalog[:] = old_catalog
        lib_svc._catalog_by_id.clear()
        lib_svc._catalog_by_id.update(old_map)


# ────── /validate 엔드포인트 ──────


@pytest.mark.asyncio
async def test_validate_endpoint_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/libraries/validate", json={"library_ids": ["python311"]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_validate_endpoint_compatible(client, mock_conn):
    resp = await client.post("/api/libraries/validate", json={"library_ids": ["python311", "torch"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["compatible"] is True
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_validate_endpoint_unknown_library(client, mock_conn):
    resp = await client.post("/api/libraries/validate", json={"library_ids": ["nonexistent"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["compatible"] is False
    assert any("알 수 없는" in m for m in data["messages"])


# ────── license_type / max_concurrent_mounts 필드 ──────


def test_library_config_license_fields_default_none():
    """LibraryConfig의 license_type과 max_concurrent_mounts 기본값은 None."""
    from app.models.storage import LibraryConfig

    lib = LibraryConfig(id="x", name="X", version="1.0", packages=[])
    assert lib.license_type is None
    assert lib.max_concurrent_mounts is None


def test_library_config_license_fields_serialized():
    """LibraryConfig 직렬화 시 license_type과 max_concurrent_mounts 포함."""
    from app.models.storage import LibraryConfig

    lib = LibraryConfig(
        id="x",
        name="X",
        version="1.0",
        packages=[],
        license_type="MIT",
        max_concurrent_mounts=10,
    )
    d = lib.model_dump()
    assert d["license_type"] == "MIT"
    assert d["max_concurrent_mounts"] == 10


@pytest.mark.asyncio
async def test_list_libraries_response_includes_license_fields(client, mock_conn):
    """GET /api/libraries 응답에 license_type과 max_concurrent_mounts 포함."""
    from app.models.storage import LibraryConfig

    test_lib = LibraryConfig(
        id="testlib",
        name="Test",
        version="1.0",
        packages=[],
        license_type="commercial",
        max_concurrent_mounts=5,
    )
    with patch("app.api.common.libraries.lib_svc") as mock_lib, patch("app.api.common.libraries.manila") as mock_manila:
        mock_lib.get_all.return_value = [test_lib]
        mock_manila.list_file_storages.return_value = []
        resp = await client.get("/api/libraries")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["license_type"] == "commercial"
    assert data[0]["max_concurrent_mounts"] == 5
