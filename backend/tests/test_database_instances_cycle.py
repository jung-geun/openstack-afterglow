"""trove 서비스 함수 create → get → delete 사이클 단위 테스트.

FastAPI 라우터/인증을 우회하고 trove.py 서비스 함수를 직접 호출.
목적: 정상 경로 페이로드 구조 회귀 방지 + Trove fault ID 노출 검증.
"""

from unittest.mock import MagicMock

import pytest

from app.services import trove

# ---------------------------------------------------------------------------
# 공통 mock 헬퍼
# ---------------------------------------------------------------------------


def _mock_create_resp(instance_id: str = "inst-abc", name: str = "test-db", status: str = "BUILD") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.text = f'{{"instance": {{"id": "{instance_id}", "name": "{name}", "status": "{status}"}}}}'
    resp.json.return_value = {"instance": {"id": instance_id, "name": name, "status": status}}
    return resp


def _mock_get_instance(instance_id: str = "inst-abc", name: str = "test-db", status: str = "ACTIVE") -> MagicMock:
    obj = MagicMock()
    obj.id = instance_id
    obj.name = name
    obj.status = status
    obj.flavor = {"id": "5", "ram": 8192}
    obj.volume = {"size": 10}
    obj.datastore = {"type": "mariadb", "version": "10.11"}
    obj.created_at = "2026-01-01T00:00:00"
    obj.hostname = ""
    obj.addresses = {}
    obj.links = []
    return obj


def _make_conn(instance_id: str = "inst-abc") -> MagicMock:
    conn = MagicMock()
    conn.database.post.return_value = _mock_create_resp(instance_id)
    conn.database.get_instance.return_value = _mock_get_instance(instance_id)
    conn.database.delete_instance.return_value = None
    return conn


# ---------------------------------------------------------------------------
# 1. create → get → delete 전체 사이클
# ---------------------------------------------------------------------------


def test_create_get_delete_cycle():
    instance_id = "inst-cycle-001"
    conn = _make_conn(instance_id)

    # create
    result = trove.create_instance(
        conn,
        name="test-db",
        flavor_id="5",
        volume_size=10,
        datastore_type="mariadb",
        datastore_version="10.11",
    )
    assert result["id"] == instance_id
    assert result["name"] == "test-db"
    assert result["status"] == "BUILD"

    # get
    fetched = trove.get_instance(conn, instance_id)
    assert fetched["id"] == instance_id
    assert fetched["status"] == "ACTIVE"

    # delete
    trove.delete_instance(conn, instance_id)
    conn.database.delete_instance.assert_called_once_with(instance_id, ignore_missing=False)


# ---------------------------------------------------------------------------
# 2. 최소 페이로드 — 선택 필드 미포함 보장
# ---------------------------------------------------------------------------


def test_create_minimal_payload():
    """필수 인자만 전달 시 volume.type, nics, locality, databases 등 키가 없어야 한다."""
    conn = _make_conn()
    trove.create_instance(
        conn,
        name="minimal",
        flavor_id="3",
        volume_size=5,
        datastore_type="mysql",
        datastore_version="8.0",
    )

    call_args = conn.database.post.call_args
    payload = call_args.kwargs.get("json") or call_args.args[1]
    body = payload["instance"]

    assert "type" not in body["volume"], "기본값 선택 시 volume.type 은 payload 에 없어야 함"
    assert "nics" not in body
    assert "locality" not in body
    assert "databases" not in body
    assert "users" not in body
    assert "availability_zone" not in body
    assert "restorePoint" not in body
    assert "configuration" not in body
    assert "replica_of" not in body


# ---------------------------------------------------------------------------
# 3. volume_type 명시 시 payload 에 포함됨 (검증 안 함 — 그대로 통과)
# ---------------------------------------------------------------------------


def test_create_with_volume_type_passes_through():
    """사용자가 명시한 volume_type 은 payload 에 포함된다.
    Trove 와 호환 여부는 우리가 검증하지 않는 결정을 명시한다."""
    conn = _make_conn()
    trove.create_instance(
        conn,
        name="db-with-type",
        flavor_id="5",
        volume_size=50,
        datastore_type="mariadb",
        datastore_version="10.11",
        volume_type="ceph_hdd",
    )

    call_args = conn.database.post.call_args
    payload = call_args.kwargs.get("json") or call_args.args[1]
    assert payload["instance"]["volume"].get("type") == "ceph_hdd"


# ---------------------------------------------------------------------------
# 4. Trove fault ID 가 RuntimeError 에 포함됨
# ---------------------------------------------------------------------------


def test_create_propagates_trove_fault_id():
    """Trove 응답에 instanceFault.message 의 UUID 가 RuntimeError 메시지에 포함되어야 한다."""
    fault_id = "28f47e2b-3d11-4f35-bb32-202b8b2999fc"
    conn = MagicMock()
    resp = MagicMock()
    resp.status_code = 500
    resp.text = f'{{"instanceFault": {{"code": 500, "message": "Internal Server Error. Please keep this ID to help us figure out what went wrong: ({fault_id})."}}}}'
    resp.json.return_value = {
        "instanceFault": {
            "code": 500,
            "message": f"Internal Server Error. Please keep this ID to help us figure out what went wrong: ({fault_id}).",
        }
    }
    conn.database.post.return_value = resp

    with pytest.raises(RuntimeError) as exc_info:
        trove.create_instance(
            conn,
            name="failing-db",
            flavor_id="5",
            volume_size=50,
            datastore_type="mariadb",
            datastore_version="10.11",
        )

    assert fault_id in str(exc_info.value), "RuntimeError 메시지에 Trove fault ID 가 포함되어야 함"
    assert "Trove 생성 실패" in str(exc_info.value)
