"""Phase 53l — /api/admin/instances/health GPU 카운트 버그 수정 검증."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _patch_redis():
    from app.services import cache as cache_mod

    fake = AsyncMock()
    fake.get.return_value = None
    fake.setex.return_value = None
    fake.delete.return_value = None
    return patch.object(cache_mod, "_get_client", return_value=fake)


def _make_server(server_id: str, name: str, flavor: dict, status: str = "ACTIVE") -> dict:
    return {
        "id": server_id,
        "name": name,
        "status": status,
        "tenant_id": "proj-1",
        "OS-EXT-SRV-ATTR:host": "nova-host-1",
        "flavor": flavor,
    }


# ---------------------------------------------------------------------------
# original_name 으로 GPU 검출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_count_detects_by_original_name(admin_client, mock_conn):
    """flavor.original_name 에 'gpu' 포함 시 gpu_count=1."""
    server = _make_server("s1", "sunmin", {"original_name": "gpu.2000Ada_8c_32g"})
    mock_conn.session.get.return_value.json.return_value = {"servers": [server]}
    with _patch_redis():
        resp = await admin_client.get("/api/admin/instances/health")

    assert resp.status_code == 200
    assert resp.json()["gpu_count"] == 1


# ---------------------------------------------------------------------------
# pci_passthrough:alias 로 GPU 검출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_count_detects_by_pci_alias(admin_client, mock_conn):
    """extra_specs.pci_passthrough:alias 에 GPU 디바이스가 있으면 gpu_count=1."""
    flavor = {"original_name": "cpu.8c_32g", "extra_specs": {"pci_passthrough:alias": "nvidia_l40s:1"}}
    server = _make_server("s2", "gpu-vm", flavor)
    mock_conn.session.get.return_value.json.return_value = {"servers": [server]}
    with _patch_redis():
        resp = await admin_client.get("/api/admin/instances/health")

    assert resp.status_code == 200
    assert resp.json()["gpu_count"] == 1


# ---------------------------------------------------------------------------
# audio-only alias 는 GPU 로 카운트하지 않음
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_count_ignores_audio_pci_alias(admin_client, mock_conn):
    """pci_passthrough:alias 에 audio 디바이스만 있으면 gpu_count=0."""
    flavor = {"original_name": "cpu.8c_32g", "extra_specs": {"pci_passthrough:alias": "gpu_audio:1"}}
    server = _make_server("s3", "audio-vm", flavor)
    mock_conn.session.get.return_value.json.return_value = {"servers": [server]}
    with _patch_redis():
        resp = await admin_client.get("/api/admin/instances/health")

    assert resp.status_code == 200
    assert resp.json()["gpu_count"] == 0


# ---------------------------------------------------------------------------
# CPU 플레이버는 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_count_zero_for_cpu_flavor(admin_client, mock_conn):
    """일반 CPU 플레이버는 gpu_count 에 포함되지 않는다."""
    server = _make_server("s4", "cpu-vm", {"original_name": "cpu.4c_8g"})
    mock_conn.session.get.return_value.json.return_value = {"servers": [server]}
    with _patch_redis():
        resp = await admin_client.get("/api/admin/instances/health")

    assert resp.status_code == 200
    assert resp.json()["gpu_count"] == 0


# ---------------------------------------------------------------------------
# Nova 호출 시 마이크로버전 2.53 헤더 송신 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_microversion_header_sent(admin_client, mock_conn):
    """GET /servers/detail 호출 시 OpenStack-API-Version: compute 2.53 헤더 포함."""
    mock_conn.session.get.return_value.json.return_value = {"servers": []}
    with _patch_redis():
        resp = await admin_client.get("/api/admin/instances/health")

    assert resp.status_code == 200
    # session.get 호출 중 헤더가 포함된 호출이 있는지 확인
    calls = mock_conn.session.get.call_args_list
    assert any((call.kwargs.get("headers") or {}).get("OpenStack-API-Version") == "compute 2.53" for call in calls), (
        "Nova /servers/detail 호출에 compute 2.53 마이크로버전 헤더가 없음"
    )
