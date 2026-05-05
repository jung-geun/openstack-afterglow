"""trove.create_instance — locality safety net 단위 테스트."""

from unittest.mock import MagicMock, patch
import pytest

from app.services import trove


def _make_conn():
    conn = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"instance": {"id": "inst-1", "name": "test", "status": "BUILD"}}'
    resp.json.return_value = {"instance": {"id": "inst-1", "name": "test", "status": "BUILD"}}
    conn.database.post.return_value = resp
    return conn


def test_locality_stripped_without_replica_context(caplog):
    """standalone 인스턴스 생성 시 locality 가 payload 에서 제거되어야 한다."""
    conn = _make_conn()
    import logging

    with caplog.at_level(logging.WARNING, logger="app.services.trove"):
        result = trove.create_instance(
            conn,
            name="test-postgres",
            flavor_id="5",
            volume_size=50,
            datastore_type="postgresql",
            datastore_version="16",
            locality="anti-affinity",
            replica_of=None,
            replica_count=None,
        )

    call_args = conn.database.post.call_args
    payload = call_args.kwargs.get("json") or call_args.args[1] if call_args.args else call_args.kwargs["json"]
    assert "locality" not in payload["instance"], "locality가 payload에 포함되면 안 됩니다"
    assert result["id"] == "inst-1"
    assert any("locality" in r.message and "무시" in r.message for r in caplog.records), \
        "WARN 로그가 기록되어야 합니다"


def test_locality_kept_with_replica_context():
    """replica_of 가 있으면 locality 가 payload 에 포함되어야 한다."""
    conn = _make_conn()
    trove.create_instance(
        conn,
        name="replica-1",
        flavor_id="5",
        volume_size=10,
        datastore_type="postgresql",
        datastore_version="16",
        locality="anti-affinity",
        replica_of="source-inst-id",
    )

    call_args = conn.database.post.call_args
    payload = call_args.kwargs.get("json") or call_args.kwargs["json"]
    assert payload["instance"].get("locality") == "anti-affinity", "replica context에서는 locality가 유지되어야 합니다"


def test_no_locality_field_when_not_provided():
    """locality 미제공 시 payload 에 키 자체가 없어야 한다."""
    conn = _make_conn()
    trove.create_instance(
        conn,
        name="plain-db",
        flavor_id="5",
        volume_size=10,
        datastore_type="mysql",
        datastore_version="8.0",
    )

    call_args = conn.database.post.call_args
    payload = call_args.kwargs.get("json") or call_args.kwargs["json"]
    assert "locality" not in payload["instance"]
