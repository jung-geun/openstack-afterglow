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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/libraries/file-storages")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_prebuilt_file_storages_success(client, mock_conn):
    with patch("app.api.common.libraries.manila") as mock_manila:
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
    old_catalog = lib_svc.LIBRARY_CATALOG[:]
    old_map = dict(lib_svc._catalog_by_id)
    try:
        restricted = LibraryConfig(
            id="restricted_lib",
            name="Restricted Lib",
            version="1.0",
            packages=[],
            ubuntu_versions=["22.04"],
        )
        lib_svc.LIBRARY_CATALOG.append(restricted)
        lib_svc._catalog_by_id["restricted_lib"] = restricted

        msgs = lib_svc.validate_compatibility(["restricted_lib"], ubuntu_version="24.04")
        assert any("24.04" in m for m in msgs)
    finally:
        lib_svc.LIBRARY_CATALOG[:] = old_catalog
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

    old_catalog = lib_svc.LIBRARY_CATALOG[:]
    old_map = dict(lib_svc._catalog_by_id)
    try:
        py312 = LibraryConfig(
            id="python312",
            name="Python 3.12",
            version="3.12",
            packages=[],
        )
        lib_svc.LIBRARY_CATALOG.append(py312)
        lib_svc._catalog_by_id["python312"] = py312

        conflict = lib_svc.check_python_version_conflict(["python311", "python312"])
        assert conflict is not None
        assert "충돌" in conflict
    finally:
        lib_svc.LIBRARY_CATALOG[:] = old_catalog
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
