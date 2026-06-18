"""Phase 50c — 관리자 대시보드 endpoint 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patch_redis():
    from app.services import cache as cache_mod

    fake = AsyncMock()
    fake.get.return_value = None
    fake.setex.return_value = None
    fake.delete.return_value = None
    return patch.object(cache_mod, "_get_client", return_value=fake)


# ---------------------------------------------------------------------------
# GET /api/admin/notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notifications_non_admin_returns_403(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/notifications")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notifications_returns_structure(admin_client, mock_conn):
    mock_conn.session.get.return_value.json.return_value = {"servers": []}
    mock_conn.compute.hypervisors.return_value = []
    mock_conn.network.ips.return_value = []
    mock_conn.network.networks.return_value = []
    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/notifications")

    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    assert "total" in data
    assert isinstance(data["notifications"], list)


@pytest.mark.asyncio
async def test_notifications_error_instances_trigger_alert(admin_client, mock_conn):
    """ERROR 인스턴스가 있으면 알림 목록에 포함."""
    error_server = {"id": "s1", "status": "ERROR", "name": "bad-vm"}
    mock_conn.session.get.return_value.json.return_value = {"servers": [error_server]}
    mock_conn.compute.hypervisors.return_value = []
    mock_conn.network.ips.return_value = []
    mock_conn.network.networks.return_value = []
    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/notifications")

    assert resp.status_code == 200
    notifs = resp.json()["notifications"]
    assert any(n["type"] == "error" for n in notifs)


# ---------------------------------------------------------------------------
# GET /api/admin/instances/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instances_health_non_admin_returns_403(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/instances/health")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_instances_health_returns_list(admin_client, mock_conn):
    mock_conn.session.get.return_value.json.return_value = {
        "servers": [
            {
                "id": "s1",
                "name": "vm-1",
                "status": "ACTIVE",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "host1",
                "flavor": {},
            },
            {
                "id": "s2",
                "name": "vm-err",
                "status": "ERROR",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "host1",
                "flavor": {},
            },
        ]
    }
    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/instances/health")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["count"] == 1  # ERROR 인스턴스 1개만
    assert data["items"][0]["status"] == "ERROR"


@pytest.mark.asyncio
async def test_instances_health_kpi_fields(admin_client, mock_conn):
    """Phase 53b: total/active/error/with_alerts/gpu_count KPI 5필드 모두 존재."""
    mock_conn.session.get.return_value.json.return_value = {
        "servers": [
            {
                "id": "s1",
                "status": "ACTIVE",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "h1",
                "name": "vm-1",
                "flavor": {"original_name": "c2.medium"},
            },
            {
                "id": "s2",
                "status": "ACTIVE",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "h1",
                "name": "vm-2",
                "flavor": {"original_name": "gpu.large"},
            },
            {
                "id": "s3",
                "status": "ERROR",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "h2",
                "name": "vm-err",
                "flavor": {},
            },
            {
                "id": "s4",
                "status": "SHUTOFF",
                "tenant_id": "p1",
                "OS-EXT-SRV-ATTR:host": "h2",
                "name": "vm-off",
                "flavor": {},
            },
        ]
    }
    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/instances/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["active"] == 2
    assert data["error"] == 1
    assert data["with_alerts"] == 1  # ERROR 수와 동일
    assert data["gpu_count"] == 1  # gpu.large 1개
    assert data["count"] == 1  # ERROR 목록 호환


@pytest.mark.asyncio
async def test_instances_health_empty(admin_client, mock_conn):
    """서버 없을 때 KPI 0 반환."""
    mock_conn.session.get.return_value.json.return_value = {"servers": []}
    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/instances/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["active"] == 0
    assert data["error"] == 0
    assert data["gpu_count"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# POST /api/admin/instances/bulk-action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_action_non_admin_returns_403(non_admin_client):
    resp = await non_admin_client.post(
        "/api/v1/admin/instances/bulk-action",
        json={"instance_ids": ["s1"], "action": "stop"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_bulk_action_stop_records_activity(admin_client, mock_conn):
    """stop 동작 수행 시 ActivityLog 기록 확인."""
    mock_conn.compute.get_server.return_value = MagicMock(id="s1")
    mock_conn.compute.stop_server.return_value = None

    with patch("app.api.identity.admin_dashboard.rec", new_callable=AsyncMock) as mock_rec:
        resp = await admin_client.post(
            "/api/v1/admin/instances/bulk-action",
            json={"instance_ids": ["s1", "s2"], "action": "stop"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] + data["failed"] == 2
    assert mock_rec.call_count == 2  # 인스턴스 수만큼 기록


@pytest.mark.asyncio
async def test_bulk_action_empty_ids_returns_400(admin_client, mock_conn):
    resp = await admin_client.post(
        "/api/v1/admin/instances/bulk-action",
        json={"instance_ids": [], "action": "start"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_action_too_many_ids_returns_400(admin_client, mock_conn):
    resp = await admin_client.post(
        "/api/v1/admin/instances/bulk-action",
        json={"instance_ids": [f"s{i}" for i in range(51)], "action": "start"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_action_partial_failure_still_records_all(admin_client, mock_conn):
    """일부 실패해도 성공/실패 모두 ActivityLog에 기록."""

    def _fail_on_s2(instance_id):
        if instance_id == "s2":
            raise RuntimeError("서버 없음")
        return MagicMock(id=instance_id)

    mock_conn.compute.get_server.side_effect = _fail_on_s2
    mock_conn.compute.stop_server.return_value = None

    with patch("app.api.identity.admin_dashboard.rec", new_callable=AsyncMock) as mock_rec:
        resp = await admin_client.post(
            "/api/v1/admin/instances/bulk-action",
            json={"instance_ids": ["s1", "s2"], "action": "stop"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] == 1
    assert data["failed"] == 1
    assert mock_rec.call_count == 2


# ---------------------------------------------------------------------------
# GET /api/admin/floating-ips/pool-stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fip_pool_stats_non_admin_returns_403(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/floating-ips/pool-stats")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_fip_pool_stats_returns_structure(admin_client, mock_conn):
    net = MagicMock()
    net.id = "net1"
    net.name = "external"
    mock_conn.network.networks.return_value = [net]

    fip1 = MagicMock()
    fip1.floating_network_id = "net1"
    fip1.port_id = "port1"
    fip2 = MagicMock()
    fip2.floating_network_id = "net1"
    fip2.port_id = None
    mock_conn.network.ips.return_value = [fip1, fip2]

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/floating-ips/pool-stats")

    assert resp.status_code == 200
    data = resp.json()
    assert "pools" in data
    assert data["count"] >= 1
    pool = next(p for p in data["pools"] if p["network_id"] == "net1")
    assert pool["total"] == 2
    assert pool["in_use"] == 1
    assert pool["util_pct"] == 50.0


# ---------------------------------------------------------------------------
# GET /api/admin/identity/summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identity_summary_non_admin_returns_403(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/identity/summary")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_identity_summary_returns_counts(admin_client, mock_conn):
    u1, u2 = MagicMock(is_enabled=True), MagicMock(is_enabled=False)
    mock_conn.identity.users.return_value = [u1, u2]
    mock_conn.identity.projects.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_conn.identity.roles.return_value = [MagicMock(id="r1", name="admin")]
    mock_conn.identity.groups.return_value = []
    mock_conn.identity.domains.return_value = [MagicMock()]

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/identity/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["counts"]["users"] == 2
    assert data["counts"]["users_enabled"] == 1
    assert data["counts"]["projects"] == 3
    assert data["counts"]["roles"] == 1
    assert "top_roles" in data
    assert data.get("partial") is False
    # Phase 52c: flat alias 검증
    assert data["user_count"] == 2
    assert data["project_count"] == 3
    assert data["role_count"] == 1
    assert "recent_users" in data
    assert "recent_projects" in data


@pytest.mark.asyncio
async def test_identity_summary_partial_when_users_fails(admin_client, mock_conn):
    """users 조회 실패 시 200 응답 + partial=True + users count=0."""
    mock_conn.identity.users.side_effect = Exception("403 Forbidden")
    mock_conn.identity.projects.return_value = [MagicMock(), MagicMock()]
    mock_conn.identity.roles.return_value = [MagicMock(id="r1", name="admin")]
    mock_conn.identity.groups.return_value = []
    mock_conn.identity.domains.return_value = []

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/identity/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["partial"] is True
    assert data["counts"]["users"] == 0
    assert data["counts"]["projects"] == 2
    assert data["user_count"] == 0
    assert data["recent_users"] == []


@pytest.mark.asyncio
async def test_identity_summary_partial_when_roles_fails(admin_client, mock_conn):
    """roles 조회 실패 시 200 응답 + partial=True + roles count=0 + partial_reasons 포함."""
    u1 = MagicMock(is_enabled=True)
    mock_conn.identity.users.return_value = [u1]
    mock_conn.identity.projects.return_value = [MagicMock()]
    mock_conn.identity.roles.side_effect = Exception("roles unavailable")
    mock_conn.identity.groups.return_value = []
    mock_conn.identity.domains.return_value = []

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/identity/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["partial"] is True
    assert data["counts"]["roles"] == 0
    assert data["counts"]["users"] == 1
    # Phase 53d: partial_reasons 필드 존재 + roles 항목 포함
    assert "partial_reasons" in data
    assert any("roles" in r for r in data["partial_reasons"])


@pytest.mark.asyncio
async def test_identity_summary_partial_reasons_403_classified(admin_client, mock_conn):
    """HTTP 403 예외 시 insufficient_privileges로 분류."""
    mock_conn.identity.users.return_value = []
    mock_conn.identity.projects.return_value = []
    mock_conn.identity.roles.side_effect = Exception("HTTP 403 Forbidden: policy")
    mock_conn.identity.groups.return_value = []
    mock_conn.identity.domains.return_value = []

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/identity/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["partial"] is True
    reasons = data.get("partial_reasons", [])
    assert any("insufficient_privileges" in r for r in reasons)


@pytest.mark.asyncio
async def test_identity_summary_no_partial_reasons_when_success(admin_client, mock_conn):
    """정상 조회 시 partial=False + partial_reasons=[]."""
    mock_conn.identity.users.return_value = []
    mock_conn.identity.projects.return_value = []
    mock_conn.identity.roles.return_value = []
    mock_conn.identity.groups.return_value = []
    mock_conn.identity.domains.return_value = []

    with _patch_redis():
        resp = await admin_client.get("/api/v1/admin/identity/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["partial"] is False
    assert data.get("partial_reasons", []) == []
