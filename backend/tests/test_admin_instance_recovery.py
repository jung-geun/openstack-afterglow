"""ERROR 인스턴스 복구 — 진단·안전 게이트·실행 순서·권한 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import instance_recovery

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

_SERVER_ID = "server-abc-123"
_VOL_ID = "vol-stuck-111"
_VOL_ID2 = "vol-stuck-222"


def _make_server(
    status: str = "ERROR",
    task_state=None,
    flavor_disk: int = 0,
    image_id: str | None = None,
    fault: dict | None = None,
    compute_host: str = "compute1",
):
    srv = MagicMock()
    srv.id = _SERVER_ID
    srv.name = "test-vm"
    srv.status = status
    srv.task_state = task_state
    srv.vm_state = status.lower()
    srv.compute_host = compute_host
    srv.fault = fault or {"message": "test fault", "code": 500, "created": "2026-01-01"}
    flavor = MagicMock()
    flavor.disk = flavor_disk
    if isinstance(srv.flavor, MagicMock):
        srv.flavor = {"disk": flavor_disk, "id": "flavor-1"}
    srv.image = {"id": image_id} if image_id else {}
    return srv


def _make_migration(
    status: str = "error",
    migration_type: str = "migration",
    source: str = "compute9",
    dest: str = "compute12",
):
    m = MagicMock()
    m.id = "mig-1"
    m.status = status
    m.migration_type = migration_type
    m.source_compute = source
    m.dest_compute = dest
    m.created_at = "2026-01-01T00:00:00Z"
    return m


def _make_port(status: str = "ACTIVE", vif_type: str = "ovs"):
    p = MagicMock()
    p.id = "port-1"
    p.status = status
    p.binding_vif_type = vif_type
    return p


def _make_vol_info(status: str = "in-use", bootable: bool = True):
    v = MagicMock()
    v.id = _VOL_ID
    v.status = status
    v.is_bootable = bootable
    v.bootable = "true" if bootable else "false"
    v.attachments = []
    return v


def _make_conn(
    server=None,
    migrations=None,
    active_migs=None,
    ports=None,
    vol_status: str = "in-use",
):
    conn = MagicMock()
    conn.compute.get_server.return_value = server or _make_server()
    conn.compute.migrations.return_value = iter(migrations or [])
    conn.compute.server_migrations.return_value = iter(active_migs or [])
    conn.network.ports.return_value = iter(ports or [_make_port()])
    conn.block_storage.get_volume.return_value = _make_vol_info(vol_status)
    conn.block_storage.reset_volume_status = MagicMock()
    conn.compute.reset_server_state = MagicMock()
    conn.compute.reboot_server = MagicMock()
    return conn


def _make_attachments(vol_id: str = _VOL_ID):
    return [
        {
            "id": "att-1",
            "volume_id": vol_id,
            "device": "/dev/vda",
            "server_id": _SERVER_ID,
            "delete_on_termination": True,
        }
    ]


# ---------------------------------------------------------------------------
# 분석 — 시나리오 판정
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_analysis_migration_failed_volume_stuck(admin_client):
    """migration error + 볼륨 attaching → migration_failed_volume_stuck, 3 steps, auto_executable=True."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "compute12",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": {"message": "vif_type=binding_failed", "code": 500, "created": ""},
            },
        ),
        patch(
            "app.services.instance_recovery._collect_migrations",
            return_value=[
                {
                    "id": "m1",
                    "status": "error",
                    "migration_type": "migration",
                    "source_compute": "compute9",
                    "dest_compute": "compute12",
                    "created_at": "",
                },
            ],
        ),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch(
            "app.services.instance_recovery._collect_volumes",
            return_value=[
                {
                    "volume_id": _VOL_ID,
                    "device": "/dev/vda",
                    "status": "attaching",
                    "bootable": True,
                    "attachments": [],
                    "delete_on_termination": True,
                }
            ],
        ),
        patch(
            "app.services.instance_recovery._collect_ports",
            return_value=[{"id": "p1", "status": "ACTIVE", "binding_vif_type": "ovs"}],
        ),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "migration_failed_volume_stuck"
    assert body["auto_executable"] is True
    assert len(body["steps"]) == 3
    assert body["steps"][0]["action"] == "reset_volume_state"
    assert body["steps"][1]["action"] == "reset_server_state"
    assert body["steps"][2]["action"] == "hard_reboot"
    assert body["placement_note"] is not None  # compute9 언급


@pytest.mark.anyio
async def test_analysis_generic_error_no_stuck_volumes(admin_client):
    """볼륨 정상, 마이그레이션 없음 → generic_error, 2 steps."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": {"message": "err", "code": 500, "created": ""},
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch(
            "app.services.instance_recovery._collect_volumes",
            return_value=[
                {
                    "volume_id": _VOL_ID,
                    "device": "/dev/vda",
                    "status": "in-use",
                    "bootable": True,
                    "attachments": [],
                    "delete_on_termination": True,
                }
            ],
        ),
        patch(
            "app.services.instance_recovery._collect_ports",
            return_value=[{"id": "p1", "status": "ACTIVE", "binding_vif_type": "ovs"}],
        ),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario"] == "generic_error"
    assert body["auto_executable"] is True
    assert len(body["steps"]) == 2


@pytest.mark.anyio
async def test_analysis_live_migration_fail_not_auto_executable(admin_client):
    """live-migration 실패 → no_live_migration_risk 검사 fail → auto_executable=False."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": None,
            },
        ),
        patch(
            "app.services.instance_recovery._collect_migrations",
            return_value=[
                {
                    "id": "m1",
                    "status": "error",
                    "migration_type": "live-migration",
                    "source_compute": "c1",
                    "dest_compute": "c2",
                    "created_at": "",
                },
            ],
        ),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_volumes", return_value=[]),
        patch("app.services.instance_recovery._collect_ports", return_value=[]),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_executable"] is False
    failed = [c for c in body["checks"] if not c["passed"]]
    assert any(c["key"] == "no_live_migration_risk" for c in failed)


@pytest.mark.anyio
async def test_analysis_non_volume_backed_not_auto_executable(admin_client):
    """flavor disk>0 + image 있음 → volume_backed fail → auto_executable=False."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 20,
                "flavor_id": "f1",
                "image_id": "img-123",
                "fault": None,
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_volumes", return_value=[]),
        patch("app.services.instance_recovery._collect_ports", return_value=[]),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_executable"] is False
    failed = [c for c in body["checks"] if not c["passed"]]
    assert any(c["key"] == "volume_backed" for c in failed)


@pytest.mark.anyio
async def test_analysis_binding_failed_port_not_auto_executable(admin_client):
    """포트 vif_type=binding_failed 지속 → ports_healthy fail → auto_executable=False."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": None,
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_volumes", return_value=[]),
        patch(
            "app.services.instance_recovery._collect_ports",
            return_value=[{"id": "p1", "status": "DOWN", "binding_vif_type": "binding_failed"}],
        ),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_executable"] is False
    failed = [c for c in body["checks"] if not c["passed"]]
    assert any(c["key"] == "ports_healthy" for c in failed)


@pytest.mark.anyio
async def test_analysis_active_server_is_error_check_fails(admin_client):
    """ACTIVE 인스턴스 → is_error_state fail."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ACTIVE",
                "task_state": None,
                "vm_state": "active",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": None,
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_volumes", return_value=[]),
        patch("app.services.instance_recovery._collect_ports", return_value=[]),
    ):
        resp = await admin_client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_executable"] is False
    failed = [c for c in body["checks"] if not c["passed"]]
    assert any(c["key"] == "is_error_state" for c in failed)


# ---------------------------------------------------------------------------
# 실행 — 단계 순서·fail-closed·중단
# ---------------------------------------------------------------------------


def test_execute_recovery_calls_steps_in_order():
    """auto_executable=True 시 reset_volume → reset_server → hard_reboot 순서로 호출."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": None,
            },
        ),
        patch(
            "app.services.instance_recovery._collect_migrations",
            return_value=[
                {
                    "id": "m1",
                    "status": "error",
                    "migration_type": "migration",
                    "source_compute": "c9",
                    "dest_compute": "c12",
                    "created_at": "",
                },
            ],
        ),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch(
            "app.services.instance_recovery._collect_volumes",
            return_value=[
                {
                    "volume_id": _VOL_ID,
                    "device": "/dev/vda",
                    "status": "attaching",
                    "bootable": True,
                    "attachments": [],
                    "delete_on_termination": True,
                }
            ],
        ),
        patch(
            "app.services.instance_recovery._collect_ports",
            return_value=[{"id": "p1", "status": "ACTIVE", "binding_vif_type": "ovs"}],
        ),
    ):
        conn = MagicMock()
        conn.compute.get_server.return_value = MagicMock(status="ACTIVE")
        conn.block_storage.reset_volume_status = MagicMock()
        conn.compute.reset_server_state = MagicMock()
        conn.compute.reboot_server = MagicMock()

        with (
            patch("app.services.instance_recovery.cinder.reset_volume_status") as mock_cinder,
            patch("app.services.instance_recovery.nova.reset_server_state") as mock_reset,
            patch("app.services.instance_recovery.nova.reboot_server") as mock_reboot,
        ):
            result = instance_recovery.execute_recovery(conn, _SERVER_ID)

    assert result["executed"] is True
    mock_cinder.assert_called_once_with(conn, _VOL_ID, "in-use", "attached")
    mock_reset.assert_called_once_with(conn, _SERVER_ID, "active")
    mock_reboot.assert_called_once_with(conn, _SERVER_ID, "HARD")
    # 순서 검증 — cinder가 reset보다 먼저
    assert [s["action"] for s in result["steps"]] == ["reset_volume_state", "reset_server_state", "hard_reboot"]
    assert all(s["status"] == "success" for s in result["steps"])


def test_execute_recovery_raises_when_not_auto_executable():
    """auto_executable=False → ValueError 발생, 액션 미호출."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 20,
                "flavor_id": "f1",
                "image_id": "img-1",
                "fault": None,
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_volumes", return_value=[]),
        patch("app.services.instance_recovery._collect_ports", return_value=[]),
        patch("app.services.instance_recovery.cinder.reset_volume_status") as mock_c,
        patch("app.services.instance_recovery.nova.reset_server_state") as mock_r,
        patch("app.services.instance_recovery.nova.reboot_server") as mock_b,
    ):
        conn = MagicMock()
        with pytest.raises(ValueError, match="자동 복구 조건 미충족"):
            instance_recovery.execute_recovery(conn, _SERVER_ID)

    mock_c.assert_not_called()
    mock_r.assert_not_called()
    mock_b.assert_not_called()


def test_execute_recovery_stops_on_step_failure():
    """reset_server_state 실패 시 hard_reboot은 skipped."""
    with (
        patch(
            "app.services.instance_recovery._collect_server",
            return_value={
                "id": _SERVER_ID,
                "name": "vm",
                "status": "ERROR",
                "task_state": None,
                "vm_state": "error",
                "compute_host": "c1",
                "flavor_disk": 0,
                "flavor_id": "f1",
                "image_id": None,
                "fault": None,
            },
        ),
        patch("app.services.instance_recovery._collect_migrations", return_value=[]),
        patch("app.services.instance_recovery._collect_active_migrations", return_value=[]),
        patch(
            "app.services.instance_recovery._collect_volumes",
            return_value=[
                {
                    "volume_id": _VOL_ID,
                    "device": "/dev/vda",
                    "status": "in-use",
                    "bootable": True,
                    "attachments": [],
                    "delete_on_termination": True,
                }
            ],
        ),
        patch(
            "app.services.instance_recovery._collect_ports",
            return_value=[{"id": "p1", "status": "ACTIVE", "binding_vif_type": "ovs"}],
        ),
    ):
        conn = MagicMock()
        conn.compute.get_server.return_value = MagicMock(status="ACTIVE")

        with (
            patch("app.services.instance_recovery.nova.reset_server_state", side_effect=RuntimeError("nova error")),
            patch("app.services.instance_recovery.nova.reboot_server") as mock_reboot,
        ):
            result = instance_recovery.execute_recovery(conn, _SERVER_ID)

    assert result["executed"] is False
    statuses = {s["action"]: s["status"] for s in result["steps"]}
    assert statuses["reset_server_state"] == "failed"
    assert statuses["hard_reboot"] == "skipped"
    mock_reboot.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP 엔드포인트 — 권한
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_recovery_analysis_requires_admin(client):
    """일반 사용자 → 403."""
    resp = await client.get(f"/api/admin/instances/{_SERVER_ID}/recovery-analysis")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_recover_requires_admin(client):
    """일반 사용자 recover → 403."""
    resp = await client.post(f"/api/admin/instances/{_SERVER_ID}/recover")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_recover_returns_409_when_not_auto_executable(admin_client):
    """auto_executable=False 시 /recover → 409."""
    with (
        patch("app.api.identity.admin.asyncio.to_thread", new=AsyncMock(side_effect=lambda f, *a, **kw: f(*a, **kw))),
        patch("app.services.instance_recovery.execute_recovery", side_effect=ValueError("자동 복구 조건 미충족")),
    ):
        resp = await admin_client.post(f"/api/admin/instances/{_SERVER_ID}/recover")

    assert resp.status_code == 409
    assert "미충족" in resp.json()["detail"]


@pytest.mark.anyio
async def test_recover_success_returns_steps(admin_client):
    """auto_executable=True 시 /recover → 200 + steps."""
    mock_result = {
        "executed": True,
        "scenario": "generic_error",
        "steps": [
            {"action": "reset_server_state", "status": "success", "detail": ""},
            {"action": "hard_reboot", "status": "success", "detail": ""},
        ],
    }
    with (
        patch("app.api.identity.admin.asyncio.to_thread", new=AsyncMock(side_effect=lambda f, *a, **kw: f(*a, **kw))),
        patch("app.services.instance_recovery.execute_recovery", return_value=mock_result),
        patch("app.api.identity.admin.rec", new=AsyncMock()),
    ):
        resp = await admin_client.post(f"/api/admin/instances/{_SERVER_ID}/recover")

    assert resp.status_code == 200
    body = resp.json()
    assert body["executed"] is True
    assert len(body["steps"]) == 2
