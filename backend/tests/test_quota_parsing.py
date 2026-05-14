"""cinder.get_volume_quota / nova.get_project_quota — REST 파싱 단위 테스트.

회귀 방지: openstacksdk `get_quota_set(usage=True)` 가 nested dict 를 평탄화해서
모든 limit 이 -1 로 나오던 버그를, raw REST 호출로 우회한다.
"""

from unittest.mock import MagicMock

from app.services.cinder import get_volume_quota
from app.services.nova import get_project_quota


def _cinder_conn(quota_set: dict) -> MagicMock:
    conn = MagicMock()
    conn.block_storage.get_endpoint.return_value = "http://cinder:8776/v3/proj"
    resp = MagicMock()
    resp.json.return_value = {"quota_set": quota_set}
    conn.session.get.return_value = resp
    return conn


def _nova_conn(quota_set: dict) -> MagicMock:
    conn = MagicMock()
    conn.compute.get_endpoint.return_value = "http://nova:8774/v2.1"
    resp = MagicMock()
    resp.json.return_value = {"quota_set": quota_set}
    conn.session.get.return_value = resp
    return conn


def test_cinder_quota_nested_dict_parsed():
    """usage=true 응답이 nested {limit,in_use} dict 일 때 그대로 반영."""
    conn = _cinder_conn(
        {
            "volumes": {"limit": 50, "in_use": 12, "reserved": 0},
            "snapshots": {"limit": 20, "in_use": 3},
            "gigabytes": {"limit": 10000, "in_use": 4872},
            "backups": {"limit": 10, "in_use": 0},
            "backup_gigabytes": {"limit": 1000, "in_use": 0},
        }
    )
    q = get_volume_quota(conn, "proj-1")
    assert q["volumes"] == {"limit": 50, "in_use": 12}
    assert q["gigabytes"] == {"limit": 10000, "in_use": 4872}
    assert q["snapshots"] == {"limit": 20, "in_use": 3}
    # REST URL/params 검증
    args, kwargs = conn.session.get.call_args
    assert args[0].endswith("/os-quota-sets/proj-1")
    assert kwargs.get("params", {}).get("usage") == "true"


def test_cinder_quota_plain_int_treated_as_limit():
    """일부 deployment 가 usage 미지원 → plain int 만 반환하는 경우에도 limit 으로 인식."""
    conn = _cinder_conn({"volumes": 50, "gigabytes": 10000})
    q = get_volume_quota(conn, "proj-1")
    assert q["volumes"] == {"limit": 50, "in_use": 0}
    assert q["gigabytes"] == {"limit": 10000, "in_use": 0}
    # 응답에 없는 키는 기본값
    assert q["snapshots"] == {"limit": -1, "in_use": 0}


def test_cinder_quota_rest_failure_falls_back_to_limits_api():
    """REST 실패 시 limits API fallback 으로 의미있는 응답."""
    conn = MagicMock()
    conn.block_storage.get_endpoint.return_value = "http://cinder:8776/v3/proj"
    conn.session.get.side_effect = RuntimeError("boom")
    absolute = MagicMock(
        max_total_volumes=99,
        total_volumes_used=7,
        max_total_snapshots=20,
        total_snapshots_used=1,
        max_total_volume_gigabytes=5000,
        total_gigabytes_used=300,
        max_total_backups=10,
        total_backups_used=0,
        max_total_backup_gigabytes=500,
        total_backup_gigabytes_used=0,
    )
    conn.block_storage.get_limits.return_value = MagicMock(absolute=absolute)
    q = get_volume_quota(conn, "proj-1")
    assert q["volumes"] == {"limit": 99, "in_use": 7}
    assert q["gigabytes"] == {"limit": 5000, "in_use": 300}


def test_nova_quota_nested_dict_parsed():
    conn = _nova_conn(
        {
            "instances": {"limit": 20, "in_use": 5},
            "cores": {"limit": 120, "in_use": 78},
            "ram": {"limit": 393216, "in_use": 215040},
            "key_pairs": {"limit": 100, "in_use": 0},
            "server_groups": {"limit": 10, "in_use": 0},
        }
    )
    q = get_project_quota(conn, "proj-1")
    assert q["instances"] == {"limit": 20, "in_use": 5}
    assert q["cores"] == {"limit": 120, "in_use": 78}
    assert q["ram"] == {"limit": 393216, "in_use": 215040}
    args, _ = conn.session.get.call_args
    assert args[0].endswith("/os-quota-sets/proj-1/detail")


def test_nova_quota_rest_failure_falls_back_to_limits_api():
    conn = MagicMock()
    conn.compute.get_endpoint.return_value = "http://nova:8774/v2.1"
    conn.session.get.side_effect = RuntimeError("boom")
    absolute = MagicMock(
        max_total_instances=20,
        total_instances_used=5,
        max_total_cores=120,
        total_cores_used=78,
        max_total_ram_size=393216,
        total_ram_used=215040,
        max_total_keypairs=100,
        max_server_groups=10,
    )
    conn.compute.get_limits.return_value = MagicMock(absolute=absolute)
    q = get_project_quota(conn, "proj-1")
    assert q["instances"] == {"limit": 20, "in_use": 5}
    assert q["cores"] == {"limit": 120, "in_use": 78}
    assert q["ram"] == {"limit": 393216, "in_use": 215040}
