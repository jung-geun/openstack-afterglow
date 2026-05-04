"""인스턴스 메트릭 엔드포인트 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PROJECT_ID = "test-project-123"

_FAKE_INSTANCE = MagicMock(
    id="inst-1",
    name="vm-1",
    project_id=_PROJECT_ID,
    flavor_name="m1.large",
    ip_addresses=[MagicMock(addr="10.0.0.1", type="fixed")],
)

_OTHER_INSTANCE = MagicMock(
    id="inst-other",
    name="vm-other",
    project_id="other-project",
    flavor_name="m1.large",
    ip_addresses=[MagicMock(addr="10.0.0.9", type="fixed")],
)

_GPU_INSTANCE = MagicMock(
    id="inst-gpu",
    name="vm-gpu",
    project_id=_PROJECT_ID,
    flavor_name="gpu.small",
    ip_addresses=[MagicMock(addr="10.0.0.2", type="fixed")],
)

_FAKE_SERIES = [{"ts": 1700000000, "value": 42.0}, {"ts": 1700000030, "value": 45.0}]


@pytest.mark.anyio
async def test_metrics_returns_series(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE), \
         patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric"] == "cpu"
    assert body["range"] == "1h"
    assert len(body["series"]) == 2
    assert body["series"][0]["value"] == 42.0


@pytest.mark.anyio
async def test_metrics_empty_series(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE), \
         patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=[])):
        resp = await client.get("/api/instances/inst-1/metrics?metric=memory&range=15m")
    assert resp.status_code == 200
    assert resp.json()["series"] == []


@pytest.mark.anyio
async def test_metrics_unauthorized_other_project(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_OTHER_INSTANCE):
        resp = await client.get("/api/instances/inst-other/metrics?metric=cpu&range=1h")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_metrics_admin_can_query_any(admin_client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_OTHER_INSTANCE), \
         patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)):
        resp = await admin_client.get("/api/instances/inst-other/metrics?metric=cpu&range=1h")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_metrics_instance_not_found(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", side_effect=Exception("not found")):
        resp = await client.get("/api/instances/bad-id/metrics?metric=cpu&range=1h")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_metrics_invalid_metric(client):
    resp = await client.get("/api/instances/inst-1/metrics?metric=invalid_xyz&range=1h")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_metrics_prom_unavailable(client):
    from app.services.prom_query import PromUnavailable
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE), \
         patch("app.api.compute.instance_metrics.query_range",
               new=AsyncMock(side_effect=PromUnavailable("conn error"))):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_metrics_gpu_on_non_gpu_instance(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE):
        resp = await client.get("/api/instances/inst-1/metrics?metric=gpu_util&range=1h")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_metrics_gpu_on_gpu_instance(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_GPU_INSTANCE), \
         patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)):
        resp = await client.get("/api/instances/inst-gpu/metrics?metric=gpu_util&range=1h")
    assert resp.status_code == 200


def test_step_calculation():
    from app.services.prom_query import calc_step
    assert calc_step(900) == 15     # 15m → 900/200=4.5 → max(15,4)=15
    assert calc_step(3600) == 18    # 1h → 3600/200=18
    assert calc_step(86400) == 432  # 24h → 86400/200=432
