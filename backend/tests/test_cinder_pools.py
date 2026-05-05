"""cinder.list_storage_pools — 풀 용량 정규화 단위 테스트."""

from unittest.mock import MagicMock

from app.services.cinder import _safe_float, list_storage_pools


def _make_conn(pools: list[dict]) -> MagicMock:
    conn = MagicMock()
    conn.block_storage.get_endpoint.return_value = "http://cinder:8776/v3/proj"
    resp = MagicMock()
    resp.json.return_value = {"pools": pools}
    conn.session.get.return_value = resp
    return conn


def test_normal_pool():
    conn = _make_conn(
        [
            {
                "name": "ceph_hdd@rbd",
                "capabilities": {
                    "total_capacity_gb": 1000.0,
                    "free_capacity_gb": 400.0,
                    "allocated_capacity_gb": 600.0,
                    "volume_backend_name": "rbd",
                    "storage_protocol": "ceph",
                },
            }
        ]
    )
    pools = list_storage_pools(conn)
    assert len(pools) == 1
    p = pools[0]
    assert p["total_capacity_gb"] == 1000.0
    assert p["free_capacity_gb"] == 400.0
    assert p["allocated_capacity_gb"] == 600.0


def test_infinite_capacity_normalised_to_zero():
    conn = _make_conn(
        [
            {
                "name": "lvm@lvm",
                "capabilities": {
                    "total_capacity_gb": "infinite",
                    "free_capacity_gb": "infinite",
                    "allocated_capacity_gb": 0,
                },
            }
        ]
    )
    pools = list_storage_pools(conn)
    assert pools[0]["total_capacity_gb"] == 0.0
    assert pools[0]["free_capacity_gb"] == 0.0


def test_unknown_capacity_normalised_to_zero():
    conn = _make_conn(
        [
            {
                "name": "lvm@lvm",
                "capabilities": {
                    "total_capacity_gb": "unknown",
                    "free_capacity_gb": "unknown",
                    "allocated_capacity_gb": None,
                },
            }
        ]
    )
    pools = list_storage_pools(conn)
    assert pools[0]["total_capacity_gb"] == 0.0
    assert pools[0]["free_capacity_gb"] == 0.0


def test_missing_capabilities():
    conn = _make_conn([{"name": "bare@pool"}])
    pools = list_storage_pools(conn)
    assert len(pools) == 1
    assert pools[0]["total_capacity_gb"] == 0.0


def test_multiple_pools_sum():
    conn = _make_conn(
        [
            {
                "name": "pool1",
                "capabilities": {"total_capacity_gb": 500.0, "free_capacity_gb": 100.0, "allocated_capacity_gb": 400.0},
            },
            {
                "name": "pool2",
                "capabilities": {"total_capacity_gb": 300.0, "free_capacity_gb": 50.0, "allocated_capacity_gb": 250.0},
            },
        ]
    )
    pools = list_storage_pools(conn)
    total = sum(p["total_capacity_gb"] for p in pools)
    assert total == 800.0


def test_safe_float_various():
    assert _safe_float(100) == 100.0
    assert _safe_float("200.5") == 200.5
    assert _safe_float(None) == 0.0
    assert _safe_float("infinite") == 0.0
    assert _safe_float("") == 0.0
