"""Prometheus http_sd 타깃 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_NODE_TARGET = {
    "targets": ["10.0.0.1:9100"],
    "labels": {
        "instance": "vm-1",
        "project_id": "proj-1",
        "flavor": "m1.medium",
        "gpu": "false",
        "job": "node_exporter",
    },
}

_GPU_NODE_TARGET = {
    "targets": ["10.0.1.1:9100"],
    "labels": {
        "instance": "gpu-vm",
        "project_id": "proj-1",
        "flavor": "gpu.a100x1_80gb",
        "gpu": "true",
        "job": "node_exporter",
    },
}

_GPU_DCGM_TARGET = {
    "targets": ["10.0.1.1:9400"],
    "labels": {
        "instance": "gpu-vm",
        "project_id": "proj-1",
        "flavor": "gpu.a100x1_80gb",
        "gpu": "true",
        "job": "dcgm_exporter",
    },
}


@pytest.mark.asyncio
async def test_sd_targets_valid_token_returns_targets(client, mock_conn):
    """유효한 Bearer 토큰으로 타깃 목록을 반환한다."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "secret-token"

    with (
        patch("app.api.common.sd_targets._collect_targets", return_value=[_NODE_TARGET]),
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
    ):
        resp = await client.get(
            "/api/v1/sd/prometheus/targets",
            headers={"Authorization": "Bearer secret-token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["targets"] == ["10.0.0.1:9100"]
    assert data[0]["labels"]["instance"] == "vm-1"
    assert data[0]["labels"]["project_id"] == "proj-1"
    assert data[0]["labels"]["flavor"] == "m1.medium"
    assert data[0]["labels"]["gpu"] == "false"


@pytest.mark.asyncio
async def test_sd_targets_invalid_token_returns_401(client, mock_conn):
    """잘못된 토큰 → 401."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "correct-token"

    with patch("app.api.common.sd_targets.get_settings", return_value=fake_settings):
        resp = await client.get(
            "/api/v1/sd/prometheus/targets",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sd_targets_missing_token_returns_401(client, mock_conn):
    """Authorization 헤더 없음 → 401."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "correct-token"

    with patch("app.api.common.sd_targets.get_settings", return_value=fake_settings):
        resp = await client.get("/api/v1/sd/prometheus/targets")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sd_targets_gpu_instance_produces_two_entries(client, mock_conn):
    """GPU 플레이버(gpu.*) VM은 9100 + 9400 두 타깃 그룹이 생성된다."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "tok"

    with (
        patch(
            "app.api.common.sd_targets._collect_targets",
            return_value=[_GPU_NODE_TARGET, _GPU_DCGM_TARGET],
        ),
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
    ):
        resp = await client.get(
            "/api/v1/sd/prometheus/targets",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    targets_ports = {g["targets"][0].split(":")[1] for g in data}
    assert targets_ports == {"9100", "9400"}
    for lbl in [g["labels"] for g in data]:
        assert lbl["gpu"] == "true"


@pytest.mark.asyncio
async def test_sd_targets_uses_cached_call(client, mock_conn):
    """SD 타깃 엔드포인트가 cached_call을 통해 Nova 호출 결과를 캐싱한다."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "tok"

    with (
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
        patch(
            "app.api.common.sd_targets.cached_call",
            new_callable=AsyncMock,
            return_value=[_NODE_TARGET],
        ) as mock_cached,
    ):
        resp = await client.get(
            "/api/v1/sd/prometheus/targets",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    # cached_call이 올바른 키로 호출됐는지 확인
    mock_cached.assert_called_once()
    call_args = mock_cached.call_args
    assert call_args[0][0] == "afterglow:sd:prometheus:targets"


@pytest.mark.asyncio
async def test_collect_targets_uses_config_ports():
    """_collect_targets가 settings의 node/dcgm 포트와 gpu prefix를 사용한다."""
    fake_settings = MagicMock()
    fake_settings.node_exporter_port = 9200
    fake_settings.dcgm_exporter_port = 9500
    fake_settings.gpu_flavor_prefix = "gpu-"

    fake_server = MagicMock()
    fake_server.name = "test-vm"
    fake_server.id = "vm-uuid"
    fake_server.project_id = "proj-1"
    fake_server.flavor = {"original_name": "gpu-a100", "id": "gpu-a100"}
    fake_server.addresses = {"network": [{"OS-EXT-IPS:type": "fixed", "addr": "10.0.0.1"}]}

    fake_conn = MagicMock()
    fake_conn.compute.servers.return_value = [fake_server]

    with (
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
        patch("app.api.common.sd_targets._build_admin_conn", return_value=fake_conn),
    ):
        from app.api.common.sd_targets import _collect_targets

        result = _collect_targets()

    ports = {g["targets"][0].split(":")[1] for g in result}
    assert "9200" in ports  # custom node_exporter_port
    assert "9500" in ports  # custom dcgm_exporter_port (GPU VM이므로)
