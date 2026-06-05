"""trove.create_backup — 단위 테스트."""

from unittest.mock import MagicMock

import pytest

from app.services import trove


def _make_conn(status: int = 200, body: dict | None = None):
    if body is None:
        body = {
            "backup": {
                "id": "bk-1",
                "name": "test-backup",
                "status": "NEW",
                "instance_id": "inst-1",
                "size": 0.07,
                "created": "2026-06-05T07:31:53",
            }
        }
    conn = MagicMock()
    resp = MagicMock()
    resp.status_code = status
    resp.text = str(body)
    resp.json.return_value = body
    conn.database.post.return_value = resp
    return conn


def test_create_backup_success():
    """정상 응답 시 backup dict 를 반환해야 한다."""
    conn = _make_conn()
    result = trove.create_backup(conn, "inst-1", "test-backup", "설명")

    assert result["id"] == "bk-1"
    assert result["name"] == "test-backup"
    assert result["status"] == "NEW"
    assert result["instance_id"] == "inst-1"

    call = conn.database.post.call_args
    payload = call.kwargs.get("json") or (call.args[1] if len(call.args) > 1 else None)
    assert payload["backup"]["instance"] == "inst-1"
    assert payload["backup"]["name"] == "test-backup"
    assert payload["backup"]["description"] == "설명"


def test_create_backup_no_description_omits_key():
    """description 미제공 시 payload 에 description 키가 없어야 한다."""
    conn = _make_conn()
    trove.create_backup(conn, "inst-1", "test-backup")

    call = conn.database.post.call_args
    payload = call.kwargs.get("json") or (call.args[1] if len(call.args) > 1 else None)
    assert "description" not in payload["backup"]


def test_create_backup_sync_failure_raises_runtime_error():
    """Trove 가 backup id 없는 응답을 반환하면 RuntimeError 를 raise 해야 한다."""
    conn = _make_conn(status=500, body={"error": "quota exceeded"})
    with pytest.raises(RuntimeError, match="Trove 백업 생성 실패"):
        trove.create_backup(conn, "inst-1", "test-backup")


def test_create_backup_empty_backup_key_raises_runtime_error():
    """Trove 가 빈 backup 객체를 반환하면 RuntimeError 를 raise 해야 한다."""
    conn = _make_conn(status=200, body={"backup": {}})
    with pytest.raises(RuntimeError, match="Trove 백업 생성 실패"):
        trove.create_backup(conn, "inst-1", "test-backup")


def test_create_backup_missing_backup_key_raises_runtime_error():
    """응답 body 에 backup 키 자체가 없으면 RuntimeError 를 raise 해야 한다."""
    conn = _make_conn(status=201, body={})
    with pytest.raises(RuntimeError, match="Trove 백업 생성 실패"):
        trove.create_backup(conn, "inst-1", "test-backup")
