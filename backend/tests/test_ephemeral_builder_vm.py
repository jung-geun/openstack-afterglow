"""임시 Builder VM 생성/삭제 및 smoke 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_server(server_id: str = "srv-abc", fixed_ip: str = "10.0.0.5") -> MagicMock:
    server = MagicMock()
    server.id = server_id
    server.status = "ACTIVE"
    server.addresses = {
        "internal": [
            {"addr": fixed_ip, "OS-EXT-IPS:type": "fixed"},
        ]
    }
    return server


def _make_fip(addr: str = "1.2.3.4", fip_id: str = "fip-123") -> MagicMock:
    fip = MagicMock()
    fip.floating_ip_address = addr
    fip.id = fip_id
    return fip


def _make_settings(**kwargs) -> MagicMock:
    s = MagicMock()
    s.builder_image_id = kwargs.get("builder_image_id", "img-ubuntu")
    s.builder_flavor_id = kwargs.get("builder_flavor_id", "flv-4c4g")
    s.builder_network_id = kwargs.get("builder_network_id", "net-svc")
    s.builder_floating_network_id = kwargs.get("builder_floating_network_id", "ext-net")
    s.builder_ssh_user = kwargs.get("builder_ssh_user", "ubuntu")
    s.builder_ssh_key_path = kwargs.get("builder_ssh_key_path", "/tmp/builder.key")
    s.default_network_id = kwargs.get("default_network_id", "net-default")
    return s


# ---------------------------------------------------------------------------
# _extract_fixed_ip
# ---------------------------------------------------------------------------


class TestExtractFixedIp:
    def test_returns_fixed_ip(self):
        from app.services.builder_vm import _extract_fixed_ip

        server = _make_server(fixed_ip="192.168.1.10")
        assert _extract_fixed_ip(server) == "192.168.1.10"

    def test_returns_none_when_no_fixed(self):
        from app.services.builder_vm import _extract_fixed_ip

        server = MagicMock()
        server.addresses = {
            "net": [{"addr": "1.2.3.4", "OS-EXT-IPS:type": "floating"}]
        }
        assert _extract_fixed_ip(server) is None

    def test_returns_none_when_addresses_empty(self):
        from app.services.builder_vm import _extract_fixed_ip

        server = MagicMock()
        server.addresses = {}
        assert _extract_fixed_ip(server) is None


# ---------------------------------------------------------------------------
# create_ephemeral_vm
# ---------------------------------------------------------------------------


class TestCreateEphemeralVm:
    @pytest.mark.asyncio
    async def test_raises_without_image_id(self):
        """builder_image_id 미설정 시 RuntimeError."""
        from app.services.builder_vm import create_ephemeral_vm

        svc_conn = MagicMock()
        with patch(
            "app.services.builder_vm.get_settings",
            return_value=_make_settings(builder_image_id=""),
        ):
            with pytest.raises(RuntimeError, match="image_id"):
                await create_ephemeral_vm(svc_conn)

    @pytest.mark.asyncio
    async def test_raises_without_floating_network(self):
        """builder_floating_network_id 미설정 시 RuntimeError."""
        from app.services.builder_vm import create_ephemeral_vm

        svc_conn = MagicMock()
        with patch(
            "app.services.builder_vm.get_settings",
            return_value=_make_settings(builder_floating_network_id=""),
        ):
            with pytest.raises(RuntimeError, match="floating_network_id"):
                await create_ephemeral_vm(svc_conn)

    @pytest.mark.asyncio
    async def test_create_returns_ephemeral_vm(self):
        """정상 흐름에서 EphemeralBuilderVM이 반환된다."""
        from app.services.builder_vm import EphemeralBuilderVM, create_ephemeral_vm

        server = _make_server(server_id="srv-xyz", fixed_ip="10.0.0.7")
        fip = _make_fip(addr="5.5.5.5", fip_id="fip-999")
        port = MagicMock()
        port.id = "port-abc"
        svc_conn = MagicMock()
        svc_conn.compute.create_server.return_value = server
        svc_conn.compute.get_server.return_value = server
        svc_conn.network.create_ip.return_value = fip
        svc_conn.network.ports.return_value = [port]

        with (
            patch(
                "app.services.builder_vm.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "app.services.builder_vm._ensure_ephemeral_keypair",
                new_callable=AsyncMock,
                return_value="afterglow-ephemeral-key",
            ),
            patch("app.services.builder_vm._wait_for_active", new_callable=AsyncMock),
            patch("app.services.builder_vm._wait_for_ssh", new_callable=AsyncMock),
        ):
            vm = await create_ephemeral_vm(svc_conn)

        assert isinstance(vm, EphemeralBuilderVM)
        assert vm.server_id == "srv-xyz"
        assert vm.internal_ip == "10.0.0.7"
        assert vm.host == "5.5.5.5"
        assert vm.fip_id == "fip-999"
        assert vm.username == "ubuntu"

    @pytest.mark.asyncio
    async def test_create_raises_when_no_internal_ip(self):
        """Fixed IP 없는 서버는 RuntimeError."""
        from app.services.builder_vm import create_ephemeral_vm

        server = MagicMock()
        server.id = "srv-nip"
        server.addresses = {}
        svc_conn = MagicMock()
        svc_conn.compute.create_server.return_value = server
        svc_conn.compute.get_server.return_value = server

        with (
            patch(
                "app.services.builder_vm.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "app.services.builder_vm._ensure_ephemeral_keypair",
                new_callable=AsyncMock,
                return_value="kp",
            ),
            patch("app.services.builder_vm._wait_for_active", new_callable=AsyncMock),
        ):
            with pytest.raises(RuntimeError, match="internal IP"):
                await create_ephemeral_vm(svc_conn)


# ---------------------------------------------------------------------------
# delete_ephemeral_vm
# ---------------------------------------------------------------------------


class TestDeleteEphemeralVm:
    @pytest.mark.asyncio
    async def test_delete_calls_fip_then_server(self):
        """FIP 반납 후 VM을 삭제한다."""
        from app.services.builder_vm import delete_ephemeral_vm

        svc_conn = MagicMock()
        svc_conn.network.delete_ip = MagicMock()
        svc_conn.compute.delete_server = MagicMock()

        await delete_ephemeral_vm(svc_conn, "srv-del", "fip-del")

        svc_conn.network.delete_ip.assert_called_once_with("fip-del")
        svc_conn.compute.delete_server.assert_called_once_with("srv-del")

    @pytest.mark.asyncio
    async def test_delete_skips_fip_when_none(self):
        """fip_id=None이면 FIP 반납 없이 VM만 삭제."""
        from app.services.builder_vm import delete_ephemeral_vm

        svc_conn = MagicMock()
        svc_conn.compute.delete_server = MagicMock()

        await delete_ephemeral_vm(svc_conn, "srv-del", None)

        svc_conn.network.delete_ip.assert_not_called()
        svc_conn.compute.delete_server.assert_called_once_with("srv-del")

    @pytest.mark.asyncio
    async def test_delete_tolerates_fip_failure(self):
        """FIP 반납 실패해도 VM 삭제는 계속 시도한다."""
        from app.services.builder_vm import delete_ephemeral_vm

        svc_conn = MagicMock()
        svc_conn.network.delete_ip.side_effect = Exception("network error")
        svc_conn.compute.delete_server = MagicMock()

        await delete_ephemeral_vm(svc_conn, "srv-del", "fip-bad")

        svc_conn.compute.delete_server.assert_called_once_with("srv-del")


# ---------------------------------------------------------------------------
# smoke 엔드포인트
# ---------------------------------------------------------------------------


class TestSmokeEndpoint:
    @pytest.mark.asyncio
    async def test_smoke_forbidden_for_non_admin(self, non_admin_client):
        """일반 사용자 → 403."""
        resp = await non_admin_client.post("/api/admin/libraries/builder-vm/_smoke")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_smoke_ok(self, admin_client):
        """정상 흐름: VM 생성 → SSH → 삭제, status=ok 반환."""
        from app.services.builder_vm import EphemeralBuilderVM

        mock_vm = EphemeralBuilderVM(
            server_id="srv-smoke",
            host="9.9.9.9",
            username="ubuntu",
            key_path="/tmp/k.key",
            internal_ip="10.0.0.99",
            fip_id="fip-smoke",
        )

        with (
            patch(
                "app.api.identity.admin_libraries.get_service_project_connection",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.builder_vm.create_ephemeral_vm",
                new_callable=AsyncMock,
                return_value=mock_vm,
            ),
            patch(
                "app.services.ssh_executor.run_command",
                new_callable=AsyncMock,
                return_value=(0, "ok\nhostname\n5.15.0", ""),
            ),
            patch(
                "app.services.builder_vm.delete_ephemeral_vm",
                new_callable=AsyncMock,
            ),
        ):
            resp = await admin_client.post("/api/admin/libraries/builder-vm/_smoke")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["server_id"] == "srv-smoke"
        assert data["internal_ip"] == "10.0.0.99"

    @pytest.mark.asyncio
    async def test_smoke_cleans_up_on_ssh_failure(self, admin_client):
        """SSH 실패 시에도 VM 삭제(finally)가 호출된다."""
        from app.services.builder_vm import EphemeralBuilderVM

        mock_vm = EphemeralBuilderVM(
            server_id="srv-fail",
            host="9.9.9.8",
            username="ubuntu",
            key_path="/tmp/k.key",
            internal_ip="10.0.0.98",
            fip_id="fip-fail",
        )
        mock_delete = AsyncMock()

        with (
            patch(
                "app.api.identity.admin_libraries.get_service_project_connection",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.builder_vm.create_ephemeral_vm",
                new_callable=AsyncMock,
                return_value=mock_vm,
            ),
            patch(
                "app.services.ssh_executor.run_command",
                new_callable=AsyncMock,
                return_value=(1, "", "connection refused"),
            ),
            patch("app.services.builder_vm.delete_ephemeral_vm", mock_delete),
        ):
            resp = await admin_client.post("/api/admin/libraries/builder-vm/_smoke")

        assert resp.status_code == 500
        mock_delete.assert_awaited_once()
