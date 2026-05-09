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
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric"] == "cpu"
    assert body["range"] == "1h"
    assert len(body["series"]) == 2
    assert body["series"][0]["value"] == 42.0


@pytest.mark.anyio
async def test_metrics_empty_series(client):
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=[])),
    ):
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
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_OTHER_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)),
    ):
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

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=PromUnavailable("conn error"))),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_metrics_gpu_on_non_gpu_instance(client):
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE):
        resp = await client.get("/api/instances/inst-1/metrics?metric=gpu_util&range=1h")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_metrics_gpu_on_gpu_instance(client):
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_GPU_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=_FAKE_SERIES)),
    ):
        resp = await client.get("/api/instances/inst-gpu/metrics?metric=gpu_util&range=1h")
    assert resp.status_code == 200


def test_step_calculation():
    from app.services.prom_query import calc_step

    assert calc_step(900) == 15  # 15m → 900/100=9 → max(15,9)=15
    assert calc_step(3600) == 36  # 1h  → 3600/100=36
    assert calc_step(86400) == 864  # 24h → 86400/100=864


# ---------------------------------------------------------------------------
# _build_expr — kolla-ansible OpenStack SD 라벨 스킴 회귀 방지
# ---------------------------------------------------------------------------


def test_build_expr_uses_instance_id_label():
    """모든 메트릭이 instance_id 라벨로 필터해야 한다 (IP:port 사용 금지)."""
    from app.api.compute.instance_metrics import _build_expr

    uuid = "16585e7b-cade-4136-a72a-6e55b54d5054"
    for metric in ("cpu", "memory", "network_rx", "network_tx", "disk_read", "disk_write", "gpu_util", "gpu_mem"):
        expr = _build_expr(metric, uuid)
        assert f'instance_id="{uuid}"' in expr, f"{metric}: instance_id 셀렉터 누락"
        assert ":9100" not in expr, f"{metric}: IP:port 셀렉터가 남아있음"
        assert ":9400" not in expr, f"{metric}: DCGM IP:port 셀렉터가 남아있음"


def test_build_expr_does_not_filter_by_job():
    """job 필터는 두지 않아야 한다 — internal/external 양쪽 모두 매치되어야 한다."""
    from app.api.compute.instance_metrics import _build_expr

    expr = _build_expr("cpu", "uuid-1")
    assert "job=" not in expr, "job 필터가 있으면 internal/external 한쪽만 매치됨"


def test_build_expr_cpu_shape():
    """CPU PromQL 정확한 형태 검증."""
    from app.api.compute.instance_metrics import _build_expr

    expr = _build_expr("cpu", "abc")
    expected = '100 - (avg by (instance_id) (rate(node_cpu_seconds_total{instance_id="abc",mode="idle"}[2m])) * 100)'
    assert expr == expected


# ---------------------------------------------------------------------------
# batch 엔드포인트
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_batch_returns_all_requested_metrics(client):
    """요청한 메트릭 키 모두 응답에 포함되어야 한다."""
    fake = [{"ts": 1700000000, "value": 10.0}]
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=fake)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-batch?metrics=cpu,memory&range=1h")
    assert resp.status_code == 200
    body = resp.json()
    assert "cpu" in body["metrics"]
    assert "memory" in body["metrics"]
    assert body["metrics"]["cpu"]["series"][0]["value"] == 10.0
    assert body["metrics"]["cpu"]["error"] is None


@pytest.mark.anyio
async def test_batch_per_metric_error_capsulated(client):
    """한 메트릭이 PromUnavailable 이어도 다른 메트릭은 정상 반환되어야 한다."""
    from app.services.prom_query import PromUnavailable

    fake = [{"ts": 1700000000, "value": 5.0}]
    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PromUnavailable("timeout")
        return fake

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-batch?metrics=cpu,memory&range=1h")
    assert resp.status_code == 200
    body = resp.json()
    # 첫 번째 메트릭 에러 캡슐화 — 전체 응답은 200
    errors = [v["error"] for v in body["metrics"].values() if v["error"]]
    oks = [v for v in body["metrics"].values() if not v["error"] and v["series"]]
    assert len(errors) == 1
    assert len(oks) == 1


@pytest.mark.anyio
async def test_batch_skips_gpu_on_non_gpu(client):
    """non-GPU 인스턴스에 gpu_util 요청 시 silent skip (키 누락)."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=[])),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-batch?metrics=cpu,gpu_util&range=1h")
    assert resp.status_code == 200
    body = resp.json()
    assert "cpu" in body["metrics"]
    assert "gpu_util" not in body["metrics"]


@pytest.mark.anyio
async def test_batch_invalid_metric_returns_422(client):
    """알 수 없는 메트릭 키 포함 시 422."""
    resp = await client.get("/api/instances/inst-1/metrics-batch?metrics=cpu,xyz_unknown&range=1h")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# libvirt-exporter 폴백 테스트
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_instance_metrics_cpu_fallback_to_libvirt(client):
    """node_exporter 빈 시계열 → libvirt 폴백 호출 → 시계열 반환."""
    libvirt_series = [{"ts": 1700000000, "value": 35.0}]

    async def _side_effect(expr: str, **kwargs):
        if "node_cpu_seconds_total" in expr:
            return []
        return libvirt_series

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == libvirt_series


@pytest.mark.anyio
async def test_instance_metrics_memory_fallback(client):
    """메모리 node_exporter 빈 → libvirt memory_stats_used_percent 폴백."""
    libvirt_series = [{"ts": 1700000000, "value": 68.5}]

    async def _side_effect(expr: str, **kwargs):
        if "node_memory_MemAvailable_bytes" in expr:
            return []
        return libvirt_series

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=memory&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == libvirt_series


@pytest.mark.anyio
async def test_instance_metrics_network_rx_fallback(client):
    """network_rx node_exporter 빈 → libvirt interface_stats 폴백."""
    libvirt_series = [{"ts": 1700000000, "value": 1024.0}]

    async def _side_effect(expr: str, **kwargs):
        if "node_network_receive_bytes_total" in expr:
            return []
        return libvirt_series

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=network_rx&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == libvirt_series


@pytest.mark.anyio
async def test_instance_metrics_disk_read_fallback(client):
    """disk_read node_exporter 빈 → libvirt block_stats 폴백."""
    libvirt_series = [{"ts": 1700000000, "value": 512.0}]

    async def _side_effect(expr: str, **kwargs):
        if "node_disk_read_bytes_total" in expr:
            return []
        return libvirt_series

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=disk_read&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == libvirt_series


@pytest.mark.anyio
async def test_instance_metrics_node_exporter_priority_no_fallback_call(client):
    """node_exporter 결과가 있으면 libvirt 폴백 호출 없어야 한다."""
    call_count = 0

    async def _side_effect(expr: str, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FAKE_SERIES

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(side_effect=_side_effect)),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == _FAKE_SERIES
    assert call_count == 1  # libvirt 폴백 호출 없음


@pytest.mark.anyio
async def test_instance_metrics_both_empty_returns_empty_series(client):
    """node_exporter + libvirt 모두 빈 시계열 → 빈 배열, 500 금지."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.query_range", new=AsyncMock(return_value=[])),
    ):
        resp = await client.get("/api/instances/inst-1/metrics?metric=cpu&range=1h")

    assert resp.status_code == 200
    assert resp.json()["series"] == []


def test_build_libvirt_expr_returns_single_series_format():
    """libvirt 표현식이 sum/avg by(instance_id) 로 단일 시계열을 보장해야 한다."""
    from app.api.compute.instance_metrics import _build_libvirt_expr

    uuid = "test-uuid-1234"
    for metric in ("cpu", "memory", "network_rx", "network_tx", "disk_read", "disk_write"):
        expr = _build_libvirt_expr(metric, uuid)
        assert expr is not None, f"{metric}: libvirt 표현식이 None"
        assert f'instance_id="{uuid}"' in expr, f"{metric}: instance_id 셀렉터 누락"
        assert "group_left(instance_id)" in expr, f"{metric}: group_left 조인 누락"
        assert "libvirt_domain_openstack_info" in expr, f"{metric}: openstack_info 조인 누락"

    # GPU 는 libvirt 대체 없음
    assert _build_libvirt_expr("gpu_util", uuid) is None
    assert _build_libvirt_expr("gpu_mem", uuid) is None
