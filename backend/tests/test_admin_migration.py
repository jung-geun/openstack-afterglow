"""마이그레이션 관련 백엔드 단위 테스트.

CPU 호환 호스트 필터링, 마이그레이션 상태 추적, 제어(abort/force-complete),
실패 메시지 노출, 엔드포인트 권한 검사를 검증한다.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services import nova

# ───────────────────────────────────────────────
# helpers
# ───────────────────────────────────────────────


def _make_hypervisor(hostname: str, cpu_model: str | None, state: str = "up", status: str = "enabled") -> dict:
    cpu_info: dict = {}
    if cpu_model:
        cpu_info = {"arch": "x86_64", "model": cpu_model, "vendor": "Intel"}
    return {
        "hypervisor_hostname": hostname,
        "state": state,
        "status": status,
        "cpu_info": cpu_info,
    }


def _mock_session_get(hypervisors: list[dict]):
    resp = MagicMock()
    resp.json.return_value = {"hypervisors": hypervisors}
    session = MagicMock()
    session.get.return_value = resp
    return session


# ───────────────────────────────────────────────
# list_compute_hosts — CPU 필터링
# ───────────────────────────────────────────────


def _conn_with_hypervisors(hypervisors: list[dict]) -> MagicMock:
    conn = MagicMock()
    conn.compute.get_endpoint.return_value = "http://nova:8774/v2.1"
    conn.session = _mock_session_get(hypervisors)
    return conn


def test_list_compute_hosts_no_filter():
    """source_host 없으면 up/enabled 호스트 전부 반환."""
    hypervisors = [
        _make_hypervisor("compute1", "Skylake-Server"),
        _make_hypervisor("compute2", "Cascadelake-Server"),
        _make_hypervisor("compute3", "Skylake-Server", state="down"),  # 제외
    ]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn)
    names = [r["name"] for r in result]
    assert "compute1" in names
    assert "compute2" in names
    assert "compute3" not in names  # state=down 제외


def test_list_compute_hosts_cpu_filter_same_model():
    """source_host 지정 시 동일 CPU 모델만 반환하고 source 자신 제외."""
    hypervisors = [
        _make_hypervisor("src-host", "Skylake-Server"),
        _make_hypervisor("same-cpu-1", "Skylake-Server"),
        _make_hypervisor("same-cpu-2", "Skylake-Server"),
        _make_hypervisor("diff-cpu", "Cascadelake-Server"),
    ]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn, source_host="src-host")
    names = [r["name"] for r in result]
    assert "src-host" not in names, "소스 호스트 자신은 제외"
    assert "same-cpu-1" in names
    assert "same-cpu-2" in names
    assert "diff-cpu" not in names, "CPU 불일치 호스트 제외"


def test_list_compute_hosts_cpu_model_in_result():
    """반환 dict에 cpu_model 필드가 포함된다."""
    hypervisors = [_make_hypervisor("compute1", "Skylake-Server")]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn)
    assert result[0]["cpu_model"] == "Skylake-Server"


def test_list_compute_hosts_fail_open_no_source_cpu_info():
    """소스 호스트의 cpu_info가 비어있으면 fail-open — 소스 제외 후 전체 반환."""
    hypervisors = [
        _make_hypervisor("src-host", None),  # cpu_info 없음
        _make_hypervisor("other-1", "Skylake-Server"),
        _make_hypervisor("other-2", "Cascadelake-Server"),
    ]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn, source_host="src-host")
    names = [r["name"] for r in result]
    assert "src-host" not in names
    assert "other-1" in names
    assert "other-2" in names


def test_list_compute_hosts_cpu_info_as_json_string():
    """cpu_info가 JSON 문자열로 반환되는 Nova 구버전 환경 처리."""
    h = _make_hypervisor("compute1", "IvyBridge")
    h["cpu_info"] = json.dumps({"arch": "x86_64", "model": "IvyBridge", "vendor": "Intel"})
    hypervisors = [h, _make_hypervisor("src", "IvyBridge")]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn, source_host="src")
    names = [r["name"] for r in result]
    assert "compute1" in names


def test_list_compute_hosts_disabled_excluded():
    """status=disabled 호스트는 항상 제외."""
    hypervisors = [
        _make_hypervisor("compute1", "Skylake-Server"),
        _make_hypervisor("disabled-host", "Skylake-Server", status="disabled"),
    ]
    conn = _conn_with_hypervisors(hypervisors)
    result = nova.list_compute_hosts(conn, source_host="compute1")
    assert not any(r["name"] == "disabled-host" for r in result)


# ───────────────────────────────────────────────
# _extract_os_error
# ───────────────────────────────────────────────


def test_extract_os_error_from_message_attr():
    """message 속성이 있는 예외에서 메시지 추출."""
    e = Exception("raw")
    e.message = "No valid host was found"  # type: ignore[attr-defined]
    assert nova._extract_os_error(e) == "No valid host was found"


def test_extract_os_error_from_response_json():
    """response 객체의 JSON faultstring에서 추출."""
    resp = MagicMock()
    resp.json.return_value = {"faultstring": "No valid host was found"}
    e = Exception("raw")
    e.response = resp  # type: ignore[attr-defined]
    assert "No valid host was found" in nova._extract_os_error(e)


def test_extract_os_error_fallback_to_str():
    """message/response 모두 없으면 str(e) 사용."""
    e = ValueError("something went wrong")
    assert "something went wrong" in nova._extract_os_error(e)


# ───────────────────────────────────────────────
# get_server_migration_status
# ───────────────────────────────────────────────


def _make_server_migration(
    *,
    id: str = "mig-1",
    source_compute: str = "src",
    dest_compute: str = "dst",
    dest_host: str | None = None,
    status: str = "running",
    migration_type: str = "live-migration",
    memory_total_bytes: int = 1000,
    memory_processed_bytes: int = 400,
) -> MagicMock:
    m = MagicMock()
    m.id = id
    m.source_compute = source_compute
    m.dest_compute = dest_compute
    m.dest_host = dest_host
    m.status = status
    m.migration_type = migration_type
    m.memory_total_bytes = memory_total_bytes
    m.memory_processed_bytes = memory_processed_bytes
    m.memory_remaining_bytes = memory_total_bytes - memory_processed_bytes
    return m


def test_get_server_migration_status_active():
    """MIGRATING 중 source→dest + 메모리 진행률 반환."""
    conn = MagicMock()
    srv = MagicMock()
    srv.compute_host = "src-host"
    conn.compute.get_server.return_value = srv
    conn.compute.server_migrations.return_value = [
        _make_server_migration(
            source_compute="src-host", dest_compute="dst-host", memory_total_bytes=1000, memory_processed_bytes=450
        )
    ]

    result = nova.get_server_migration_status(conn, "server-1")

    assert result["host"] == "src-host"
    assert result["migration"] is not None
    assert result["migration"]["source"] == "src-host"
    assert result["migration"]["dest"] == "dst-host"
    assert result["migration"]["memory_percent"] == 45.0
    assert result["error"] is None


def test_get_server_migration_status_dest_host_priority():
    """dest_host가 있으면 dest_compute보다 우선한다."""
    conn = MagicMock()
    srv = MagicMock()
    srv.compute_host = "src"
    conn.compute.get_server.return_value = srv
    conn.compute.server_migrations.return_value = [
        _make_server_migration(dest_compute="dst-compute", dest_host="dst-host.example.com")
    ]

    result = nova.get_server_migration_status(conn, "server-1")
    assert result["migration"]["dest"] == "dst-host.example.com"


def test_get_server_migration_status_no_active():
    """진행 중 마이그레이션 없으면 migration=None."""
    conn = MagicMock()
    srv = MagicMock()
    srv.compute_host = "compute1"
    srv.fault = None
    conn.compute.get_server.return_value = srv
    conn.compute.server_migrations.return_value = []
    conn.compute.migrations.return_value = []

    result = nova.get_server_migration_status(conn, "server-1")
    assert result["migration"] is None
    assert result["host"] == "compute1"


def test_get_server_migration_status_fault_message():
    """인스턴스 fault.message를 error로 반환."""
    conn = MagicMock()
    srv = MagicMock()
    srv.compute_host = "compute1"
    srv.fault = {"message": "No valid host was found"}
    conn.compute.get_server.return_value = srv
    conn.compute.server_migrations.return_value = []

    result = nova.get_server_migration_status(conn, "server-1")
    assert result["error"] == "No valid host was found"


def test_get_server_migration_status_memory_zero_total():
    """memory_total_bytes=0 이면 memory_percent=None (ZeroDivision 방지)."""
    conn = MagicMock()
    srv = MagicMock()
    srv.compute_host = "src"
    conn.compute.get_server.return_value = srv
    conn.compute.server_migrations.return_value = [
        _make_server_migration(memory_total_bytes=0, memory_processed_bytes=0)
    ]

    result = nova.get_server_migration_status(conn, "server-1")
    assert result["migration"]["memory_percent"] is None


# ───────────────────────────────────────────────
# abort_live_migration / force_complete_live_migration
# ───────────────────────────────────────────────


def test_abort_live_migration_with_id():
    """migration_id 명시 시 바로 abort 호출."""
    conn = MagicMock()
    nova.abort_live_migration(conn, "server-1", migration_id="mig-99")
    conn.compute.abort_server_migration.assert_called_once_with("mig-99", "server-1")


def test_abort_live_migration_auto_resolve():
    """migration_id 생략 시 server_migrations에서 자동 해석."""
    conn = MagicMock()
    active = MagicMock()
    active.id = "mig-auto"
    conn.compute.server_migrations.return_value = [active]

    nova.abort_live_migration(conn, "server-1")
    conn.compute.abort_server_migration.assert_called_once_with("mig-auto", "server-1")


def test_abort_live_migration_no_active_raises():
    """진행 중 마이그레이션 없으면 ValueError."""
    conn = MagicMock()
    conn.compute.server_migrations.return_value = []
    with pytest.raises(ValueError, match="진행 중인"):
        nova.abort_live_migration(conn, "server-1")


def test_force_complete_live_migration_with_id():
    conn = MagicMock()
    nova.force_complete_live_migration(conn, "server-1", migration_id="mig-77")
    conn.compute.force_complete_server_migration.assert_called_once_with("mig-77", "server-1")


def test_force_complete_live_migration_auto_resolve():
    conn = MagicMock()
    active = MagicMock()
    active.id = "mig-fc"
    conn.compute.server_migrations.return_value = [active]

    nova.force_complete_live_migration(conn, "server-1")
    conn.compute.force_complete_server_migration.assert_called_once_with("mig-fc", "server-1")


# ───────────────────────────────────────────────
# 엔드포인트 권한 검사 (non_admin → 403)
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compute_hosts_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/compute-hosts")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_migration_status_requires_admin(non_admin_client):
    resp = await non_admin_client.get("/api/admin/instances/inst-1/migration-status")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_abort_migration_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/live-migrate/abort")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_force_complete_migration_requires_admin(non_admin_client):
    resp = await non_admin_client.post("/api/admin/instances/inst-1/live-migrate/force-complete")
    assert resp.status_code == 403


# ───────────────────────────────────────────────
# 엔드포인트 — 실패 시 실제 에러 메시지 노출
# ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_live_migrate_error_message_exposed(admin_client, mock_conn):
    """라이브 마이그레이션 실패 시 Nova 실제 에러 메시지가 400 detail에 포함된다."""
    err = Exception("live migrate failure")
    err.message = "No valid host was found"  # type: ignore[attr-defined]

    with patch("app.api.identity.admin.nova.live_migrate_server", side_effect=err):
        resp = await admin_client.post(
            "/api/admin/instances/inst-1/live-migrate",
            json={"host": None, "block_migration": "auto"},
        )

    assert resp.status_code == 400
    assert "No valid host was found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cold_migrate_error_message_exposed(admin_client, mock_conn):
    """콜드 마이그레이션 실패 시 Nova 실제 에러 메시지가 400 detail에 포함된다."""
    err = Exception("cold migrate failure")
    err.message = "Instance is not running"  # type: ignore[attr-defined]

    with patch("app.api.identity.admin.nova.cold_migrate_server", side_effect=err):
        resp = await admin_client.post("/api/admin/instances/inst-1/cold-migrate", json={})

    assert resp.status_code == 400
    assert "Instance is not running" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_migration_status_admin_ok(admin_client, mock_conn):
    """admin은 migration-status에 접근 가능하다 (403이 아님)."""
    with patch(
        "app.api.identity.admin.nova.get_server_migration_status",
        return_value={"host": "compute1", "migration": None, "error": None},
    ):
        resp = await admin_client.get("/api/admin/instances/inst-1/migration-status")
    assert resp.status_code != 403
    assert resp.json()["host"] == "compute1"
