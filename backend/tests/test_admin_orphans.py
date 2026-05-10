"""Admin Orphan Resource Detection API 단위 테스트.

서비스 레이어 9건 + 엔드포인트 2건 = 총 11건.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import orphans

_NOW = datetime(2026, 5, 10, 0, 0, 0, tzinfo=UTC)


def _make_fip(fip_id: str, *, port_id: str | None, days_ago: int, address: str = "1.2.3.4"):
    """openstacksdk FIP resource를 흉내내는 객체."""
    f = MagicMock()
    f.id = fip_id
    f.port_id = port_id
    f.floating_ip_address = address
    f.created_at = (_NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "")
    f.project_id = "p1"
    return f


def _make_volume(
    vid: str,
    *,
    status: str = "available",
    attachments: list | None = None,
    days_ago: int = 30,
    name: str = "vol",
    size: int = 50,
):
    """openstacksdk volume resource 흉내."""
    v = MagicMock()
    v.id = vid
    v.status = status
    v.attachments = attachments or []
    v.size = size
    v.name = name
    v.created_at = (_NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "")
    v.project_id = "p1"
    return v


# ---------------------------------------------------------------------------
# 서비스 레이어 — find_orphan_floating_ips
# ---------------------------------------------------------------------------


class TestFindOrphanFloatingIps:
    def test_filters_by_port_id_null(self):
        """port_id가 있는 FIP는 제외, None인 FIP만 포함."""
        conn = MagicMock()
        conn.network.ips.return_value = [
            _make_fip("fip-attached", port_id="port-1", days_ago=10),
            _make_fip("fip-orphan", port_id=None, days_ago=20),
            _make_fip("fip-attached2", port_id="port-2", days_ago=5),
        ]
        result = orphans.find_orphan_floating_ips(conn)
        ids = [r.id for r in result]
        assert ids == ["fip-orphan"]

    def test_includes_age_days(self):
        """created_at 기반 age_days 계산이 정확한지 검증."""
        conn = MagicMock()
        conn.network.ips.return_value = [_make_fip("fip-1", port_id=None, days_ago=42)]
        with patch("app.services.orphans.datetime") as dt_mock:
            dt_mock.now.return_value = _NOW
            dt_mock.fromisoformat = datetime.fromisoformat
            result = orphans.find_orphan_floating_ips(conn)
        assert len(result) == 1
        assert result[0].age_days == 42
        assert result[0].address == "1.2.3.4"


# ---------------------------------------------------------------------------
# 서비스 레이어 — find_orphan_volumes
# ---------------------------------------------------------------------------


class TestFindOrphanVolumes:
    def test_min_age_filter(self):
        """min_age_days 미만 volume은 제외."""
        conn = MagicMock()
        conn.block_storage.volumes.return_value = [
            _make_volume("vol-young", days_ago=5),
            _make_volume("vol-old", days_ago=30),
            _make_volume("vol-borderline", days_ago=14),
        ]
        with patch("app.services.orphans.datetime") as dt_mock:
            dt_mock.now.return_value = _NOW
            dt_mock.fromisoformat = datetime.fromisoformat
            result = orphans.find_orphan_volumes(conn, min_age_days=14)
        ids = sorted(r.id for r in result)
        assert ids == ["vol-borderline", "vol-old"]
        # all_projects=True 가 SDK 호출에 포함됐는지
        kwargs = conn.block_storage.volumes.call_args.kwargs
        assert kwargs.get("all_projects") is True
        assert kwargs.get("status") == "available"

    def test_excludes_attached(self):
        """attachments != [] 인 volume은 제외 (SDK가 status=available로 필터해도 race 방지)."""
        conn = MagicMock()
        conn.block_storage.volumes.return_value = [
            _make_volume(
                "vol-attached",
                days_ago=30,
                attachments=[{"server_id": "i-1"}],
            ),
            _make_volume("vol-clean", days_ago=30),
        ]
        with patch("app.services.orphans.datetime") as dt_mock:
            dt_mock.now.return_value = _NOW
            dt_mock.fromisoformat = datetime.fromisoformat
            result = orphans.find_orphan_volumes(conn, min_age_days=14)
        assert [r.id for r in result] == ["vol-clean"]


# ---------------------------------------------------------------------------
# 서비스 레이어 — cleanup_floating_ips
# ---------------------------------------------------------------------------


class TestCleanupFloatingIps:
    def test_success(self):
        """모든 FIP 삭제 성공 → deleted[]에 모두, failed[]는 비어 있음."""
        conn = MagicMock()
        with patch("app.services.orphans.neutron.delete_floating_ip") as mock_del:
            deleted, failed = orphans.cleanup_floating_ips(conn, ["fip-a", "fip-b"])
        assert deleted == ["fip-a", "fip-b"]
        assert failed == []
        assert mock_del.call_count == 2

    def test_partial_failure(self):
        """일부 예외 → failed[]에 분리."""
        conn = MagicMock()

        def _fake_delete(_conn, fid):
            if fid == "fip-bad":
                raise RuntimeError("boom")

        with patch("app.services.orphans.neutron.delete_floating_ip", side_effect=_fake_delete):
            deleted, failed = orphans.cleanup_floating_ips(conn, ["fip-a", "fip-bad", "fip-c"])
        assert deleted == ["fip-a", "fip-c"]
        assert len(failed) == 1
        assert failed[0]["id"] == "fip-bad"
        assert "boom" in failed[0]["error"]


# ---------------------------------------------------------------------------
# 서비스 레이어 — cleanup_volumes (race-safe re-fetch)
# ---------------------------------------------------------------------------


class TestCleanupVolumes:
    def test_safety_guard_attached(self):
        """재조회 시 attachments != [] 이면 delete 호출 안 됨, failed[] 분리."""
        conn = MagicMock()
        # get_volume 호출 시 race로 attached 상태가 된 것을 흉내
        attached = MagicMock()
        attached.status = "available"
        attached.attachments = [{"server_id": "i-race"}]
        with (
            patch("app.services.orphans.cinder.get_volume", return_value=attached) as mock_get,
            patch("app.services.orphans.cinder.delete_volume") as mock_del,
        ):
            deleted, failed = orphans.cleanup_volumes(conn, ["vol-x"])
        assert deleted == []
        assert len(failed) == 1
        assert failed[0]["id"] == "vol-x"
        assert "attachments" in failed[0]["error"]
        mock_get.assert_called_once()
        mock_del.assert_not_called()

    def test_safety_guard_status(self):
        """재조회 시 status != available 이면 delete 호출 안 됨."""
        conn = MagicMock()
        in_use = MagicMock()
        in_use.status = "in-use"
        in_use.attachments = []
        with (
            patch("app.services.orphans.cinder.get_volume", return_value=in_use),
            patch("app.services.orphans.cinder.delete_volume") as mock_del,
        ):
            deleted, failed = orphans.cleanup_volumes(conn, ["vol-y"])
        assert deleted == []
        assert len(failed) == 1
        assert "status=in-use" in failed[0]["error"]
        mock_del.assert_not_called()

    def test_success(self):
        """안전 가드 통과 + delete 정상 → deleted[]에 추가."""
        conn = MagicMock()
        clean = MagicMock()
        clean.status = "available"
        clean.attachments = []
        with (
            patch("app.services.orphans.cinder.get_volume", return_value=clean),
            patch("app.services.orphans.cinder.delete_volume") as mock_del,
        ):
            deleted, failed = orphans.cleanup_volumes(conn, ["vol-z1", "vol-z2"])
        assert deleted == ["vol-z1", "vol-z2"]
        assert failed == []
        assert mock_del.call_count == 2


# ---------------------------------------------------------------------------
# 엔드포인트 — admin/orphans
# ---------------------------------------------------------------------------


class TestAdminOrphansEndpoint:
    @pytest.mark.asyncio
    async def test_endpoint_requires_admin(self, non_admin_client):
        """비관리자 GET → 403."""
        resp = await non_admin_client.get("/api/admin/orphans")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cleanup_invalid_kind_rejected(self, admin_client):
        """kind 미정의 값 → 422."""
        resp = await admin_client.post(
            "/api/admin/orphans/cleanup",
            json={"kind": "snapshot", "ids": ["x"]},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cleanup_volume_records_audit_per_id(self, admin_client):
        """volume cleanup 시 deleted/failed 각 ID마다 rec 호출 + 인자 정확."""
        # 서비스가 1 deleted + 1 failed 반환하도록 모의
        with (
            patch(
                "app.api.identity.admin_orphans.orphans.cleanup_volumes",
                return_value=(["vol-ok"], [{"id": "vol-bad", "error": "boom"}]),
            ),
            patch("app.api.identity.admin_orphans.rec", new=AsyncMock()) as mock_rec,
        ):
            resp = await admin_client.post(
                "/api/admin/orphans/cleanup",
                json={"kind": "volume", "ids": ["vol-ok", "vol-bad"]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] == ["vol-ok"]
        assert body["failed"][0]["id"] == "vol-bad"
        # rec: 2회 호출 — 1 success + 1 failed
        assert mock_rec.call_count == 2
        statuses = {c.kwargs["status"] for c in mock_rec.call_args_list}
        assert statuses == {"success", "failed"}
        # action / resource_type 검증
        for call in mock_rec.call_args_list:
            assert call.kwargs["action"] == "orphan.cleanup"
            assert call.kwargs["resource_type"] == "volume"
