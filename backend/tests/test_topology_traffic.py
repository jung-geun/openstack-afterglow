"""토폴로지 트래픽 엔드포인트 테스트."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_PROJECT_ID = "test-project-123"

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _mock_port(device_id: str, network_id: str, device_owner: str = "compute:nova"):
    p = MagicMock()
    p.device_id = device_id
    p.device_owner = device_owner
    p.network_id = network_id
    p.fixed_ips = [{"ip_address": "10.0.0.1", "subnet_id": "sub-1"}]
    return p


def _prom_instant_response(label_val_pairs: list[tuple[dict, float]]):
    """query_instant_multi 가 반환할 (labels, value) 리스트 생성."""
    return [(labels, val) for labels, val in label_val_pairs]


# ── 테스트: VM 트래픽 PromQL 매핑 ─────────────────────────────────────────────


@pytest.mark.anyio
async def test_traffic_returns_instances_from_promql(client, mock_conn):
    """VM rx/tx bps 가 응답에 포함되고 byte→bit 변환(×8)이 적용돼야 한다."""
    mock_conn.network.ports.return_value = [_mock_port("uuid-1", "net-a")]

    rx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1"}, 125_000.0),  # 125kB/s → 1Mbps
        ]
    )
    tx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1"}, 62_500.0),  # 62.5kB/s → 500kbps
        ]
    )

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[rx_pairs, tx_pairs])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert "uuid-1" in body["instances"]
    inst = body["instances"]["uuid-1"]
    assert abs(inst["rx_bps"] - 1_000_000.0) < 1
    assert abs(inst["tx_bps"] - 500_000.0) < 1


@pytest.mark.anyio
async def test_traffic_aggregates_by_network(client, mock_conn):
    """같은 네트워크에 속한 VM들의 bps 가 network 합산에 반영돼야 한다."""
    mock_conn.network.ports.return_value = [
        _mock_port("uuid-1", "net-a"),
        _mock_port("uuid-2", "net-a"),
    ]

    rx_pairs = _prom_instant_response(
        [
            ({"instance_id": "uuid-1"}, 100.0),
            ({"instance_id": "uuid-2"}, 200.0),
        ]
    )
    tx_pairs: list = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(side_effect=[rx_pairs, tx_pairs])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    net = body["networks"]["net-a"]
    assert abs(net["rx_bps"] - (100.0 + 200.0) * 8) < 1


@pytest.mark.anyio
async def test_traffic_routers_empty_with_meta(client, mock_conn):
    """routers 는 빈 dict, _meta.router_traffic 이 'exporter_required' 여야 한다."""
    mock_conn.network.ports.return_value = []

    with (
        patch("app.api.network.networks.query_instant_multi", new=AsyncMock(return_value=[])),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert body["routers"] == {}
    assert body["_meta"]["router_traffic"] == "exporter_required"


@pytest.mark.anyio
async def test_traffic_handles_no_instances(client, mock_conn):
    """인스턴스 0개여도 200 OK 반환해야 한다."""
    mock_conn.network.ports.return_value = []

    with patch("app.api.network.networks.list_load_balancers", return_value=[]):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    body = resp.json()
    assert body["instances"] == {}
    assert body["networks"] == {}


@pytest.mark.anyio
async def test_traffic_prom_unavailable_falls_back(client, mock_conn):
    """PromUnavailable 발생 시 instances={} 로 fallback — 전체 500 금지."""
    from app.services.prom_query import PromUnavailable

    mock_conn.network.ports.return_value = [_mock_port("uuid-1", "net-a")]

    with (
        patch(
            "app.api.network.networks.query_instant_multi",
            new=AsyncMock(side_effect=PromUnavailable("timeout")),
        ),
        patch("app.api.network.networks.list_load_balancers", return_value=[]),
    ):
        resp = await client.get("/api/networks/topology/traffic")

    assert resp.status_code == 200
    assert resp.json()["instances"] == {}


# ── 테스트: LB 차분 계산 ──────────────────────────────────────────────────────


def test_traffic_lb_first_call_zero():
    """최초 스냅샷 없을 때 lb_rate_from_snapshot 은 rx_bps=tx_bps=0 을 반환해야 한다."""
    from app.services import octavia

    octavia._lb_snapshot.clear()

    result = octavia.lb_rate_from_snapshot("lb-new", {"bytes_in": 1000, "bytes_out": 2000, "active_connections": 1})
    assert result["rx_bps"] == 0.0
    assert result["tx_bps"] == 0.0


def test_traffic_lb_rate_from_snapshot():
    """두 번째 호출에서 누적 차분으로 rate 를 계산해야 한다."""
    from app.services import octavia

    lb_id = "lb-rate-test"
    octavia._lb_snapshot.pop(lb_id, None)

    t0 = time.time() - 10  # 10초 전에 스냅샷이 있었다고 가정
    with octavia._snapshot_lock:
        octavia._lb_snapshot[lb_id] = (0, 0, t0)

    result = octavia.lb_rate_from_snapshot(
        lb_id, {"bytes_in": 1_250_000, "bytes_out": 2_500_000, "active_connections": 5}
    )
    # bytes_out 증분 2_500_000 bytes / 10s * 8 = 2_000_000 bps = 2 Mbps (rx)
    assert result["rx_bps"] > 0
    assert result["tx_bps"] > 0
    # bytes_in 증분 / 10s * 8: 1_250_000 / 10 * 8 = 1_000_000 bps
    assert abs(result["tx_bps"] - 1_000_000) < 50_000  # ±5% 허용 (타이밍)


# ── 테스트: query_instant_multi ───────────────────────────────────────────────


@pytest.mark.anyio
async def test_query_instant_multi_parses_results():
    """query_instant_multi 가 Prometheus JSON 에서 (labels, value) 리스트를 파싱해야 한다."""
    from unittest.mock import patch

    from app.services.prom_query import query_instant_multi

    fake_body = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"instance_id": "uuid-1"}, "value": [1700000000, "42.5"]},
                {"metric": {"instance_id": "uuid-2"}, "value": [1700000000, "10.0"]},
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_body
    mock_resp.raise_for_status = MagicMock()

    async def _mock_get(*args, **kwargs):
        return mock_resp

    with patch("app.services.prom_query._get_client") as mock_client:
        mock_client.return_value.get = _mock_get
        result = await query_instant_multi('node_cpu_seconds_total{instance_id="uuid-1"}')

    assert len(result) == 2
    labels0, val0 = result[0]
    assert labels0["instance_id"] == "uuid-1"
    assert val0 == 42.5
    labels1, val1 = result[1]
    assert labels1["instance_id"] == "uuid-2"
    assert val1 == 10.0
