"""cinder.get_volume_quota / nova.get_project_quota — REST 파싱 단위 테스트.

회귀 방지: openstacksdk `get_quota_set(usage=True)` 가 nested dict 를 평탄화해서
모든 limit 이 -1 로 나오던 버그를, raw REST 호출로 우회한다.
"""

from unittest.mock import MagicMock

import pytest

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


def test_strict_quota_mode_preserves_unlimited_and_zero_usage():
    nova_conn = _nova_conn(
        {
            "instances": {"limit": -1, "in_use": 0},
            "cores": {"limit": 0, "in_use": 0},
            "ram": {"limit": 32, "in_use": 0},
        }
    )
    cinder_conn = _cinder_conn(
        {
            "volumes": {"limit": -1, "in_use": 0},
            "gigabytes": {"limit": 0, "in_use": 0},
        }
    )

    assert get_project_quota(nova_conn, "proj-1", strict=True)["instances"] == {"limit": -1, "in_use": 0}
    assert get_project_quota(nova_conn, "proj-1", strict=True)["cores"] == {"limit": 0, "in_use": 0}
    assert get_volume_quota(cinder_conn, "proj-1", strict=True)["gigabytes"] == {"limit": 0, "in_use": 0}


def test_strict_quota_mode_rejects_malformed_data_but_legacy_falls_back():
    nova_conn = _nova_conn(
        {
            "instances": {"limit": "invalid", "in_use": 0},
            "cores": {"limit": 1, "in_use": 0},
            "ram": {"limit": 1, "in_use": 0},
        }
    )
    absolute = MagicMock(
        max_total_instances=9,
        total_instances_used=2,
        max_total_cores=9,
        total_cores_used=2,
        max_total_ram_size=9,
        total_ram_used=2,
        max_total_keypairs=1,
        max_server_groups=1,
    )
    nova_conn.compute.get_limits.return_value = MagicMock(absolute=absolute)

    with pytest.raises(ValueError):
        get_project_quota(nova_conn, "proj-1", strict=True)
    assert get_project_quota(nova_conn, "proj-1")["instances"] == {"limit": 9, "in_use": 2}


def test_legacy_quota_mode_falls_back_for_runtime_errors():
    nova_conn = MagicMock()
    nova_conn.compute.get_endpoint.return_value = "http://nova:8774/v2.1"
    nova_conn.session.get.side_effect = RuntimeError("down")
    nova_absolute = MagicMock(
        max_total_instances=4,
        total_instances_used=1,
        max_total_cores=4,
        total_cores_used=1,
        max_total_ram_size=4,
        total_ram_used=1,
        max_total_keypairs=1,
        max_server_groups=1,
    )
    nova_conn.compute.get_limits.return_value = MagicMock(absolute=nova_absolute)

    cinder_conn = MagicMock()
    cinder_conn.block_storage.get_endpoint.return_value = "http://cinder:8776/v3/proj"
    cinder_conn.session.get.side_effect = RuntimeError("down")
    cinder_absolute = MagicMock(
        max_total_volumes=4,
        total_volumes_used=1,
        max_total_snapshots=1,
        total_snapshots_used=0,
        max_total_volume_gigabytes=4,
        total_gigabytes_used=1,
        max_total_backups=1,
        total_backups_used=0,
        max_total_backup_gigabytes=1,
        total_backup_gigabytes_used=0,
    )
    cinder_conn.block_storage.get_limits.return_value = MagicMock(absolute=cinder_absolute)

    assert get_project_quota(nova_conn, "proj-1")["instances"] == {"limit": 4, "in_use": 1}
    assert get_volume_quota(cinder_conn, "proj-1")["volumes"] == {"limit": 4, "in_use": 1}


@pytest.mark.parametrize("payload", [None, [], {"quota_set": None}])
def test_strict_quota_mode_rejects_malformed_top_level_payloads(payload):
    nova_conn = _nova_conn({})
    cinder_conn = _cinder_conn({})
    nova_conn.session.get.return_value.json.return_value = payload
    cinder_conn.session.get.return_value.json.return_value = payload

    with pytest.raises(ValueError):
        get_project_quota(nova_conn, "proj-1", strict=True)
    with pytest.raises(ValueError):
        get_volume_quota(cinder_conn, "proj-1", strict=True)
