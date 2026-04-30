"""Prometheus http_sd 타깃 엔드포인트 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.compute import InstanceInfo, IpAddress


def _make_instance(
    name: str = "vm-1",
    project_id: str = "proj-1",
    flavor_name: str = "m1.medium",
    ip: str = "10.0.0.1",
    ip_type: str = "fixed",
) -> InstanceInfo:
    return InstanceInfo(
        id=f"id-{name}",
        name=name,
        status="ACTIVE",
        flavor_name=flavor_name,
        project_id=project_id,
        ip_addresses=[IpAddress(addr=ip, type=ip_type)],
    )


@pytest.mark.asyncio
async def test_sd_targets_valid_token_returns_targets(client, mock_conn):
    """유효한 Bearer 토큰으로 타깃 목록을 반환한다."""
    instances = [
        _make_instance("vm-1", "proj-1", "m1.medium", "10.0.0.1"),
    ]
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "secret-token"

    with (
        patch("app.api.common.sd_targets.nova.list_servers", return_value=instances),
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
    ):
        resp = await client.get(
            "/api/sd/prometheus/targets",
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
            "/api/sd/prometheus/targets",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sd_targets_missing_token_returns_401(client, mock_conn):
    """Authorization 헤더 없음 → 401."""
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "correct-token"

    with patch("app.api.common.sd_targets.get_settings", return_value=fake_settings):
        resp = await client.get("/api/sd/prometheus/targets")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sd_targets_gpu_instance_produces_two_entries(client, mock_conn):
    """GPU 플레이버(gpu.*) VM은 9100 + 9400 두 타깃 그룹이 생성된다."""
    instances = [
        _make_instance("gpu-vm", "proj-1", "gpu.a100x1_80gb", "10.0.1.1"),
    ]
    fake_settings = MagicMock()
    fake_settings.monitoring_sd_token = "tok"

    with (
        patch("app.api.common.sd_targets.nova.list_servers", return_value=instances),
        patch("app.api.common.sd_targets.get_settings", return_value=fake_settings),
    ):
        resp = await client.get(
            "/api/sd/prometheus/targets",
            headers={"Authorization": "Bearer tok"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    targets_ports = {g["targets"][0].split(":")[1] for g in data}
    assert targets_ports == {"9100", "9400"}
    gpu_labels = [g["labels"] for g in data]
    for lbl in gpu_labels:
        assert lbl["gpu"] == "true"
