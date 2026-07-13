"""VPN 서버 프로비저닝 오케스트레이션 테스트.

flavor 이름 해석, SG/포트/FIP 생성 흐름(OpenStack 연결 mock), 상태 전이
(CREATING→PROVISIONING→ACTIVE/ERROR), 실패 시 롤백 호출을 검증한다.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import vpn_provisioner


def _make_flavor(name: str, flavor_id: str) -> MagicMock:
    """MagicMock(name=...)는 mock의 repr을 설정할 뿐 .name 속성이 안 됨 — 명시적으로 지정."""
    f = MagicMock()
    f.name = name
    f.id = flavor_id
    return f


def _make_settings(**overrides) -> SimpleNamespace:
    base = dict(
        vpn_provider_network_id="net-provider-1",
        vpn_flavor_name="cpu.1c_2g",
        vpn_flavor_id="",
        vpn_image_id="img-ubuntu-1",
        vpn_floating_network_id="",
        vpn_callback_base_url="https://backend.example.com",
        vpn_key_name="",
        vpn_default_tunnel_cidr="10.8.0.0/24",
        vpn_default_listen_port=51820,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# flavor 이름 → ID 해석 (_resolve_flavor_id)
# ---------------------------------------------------------------------------


class TestResolveFlavorId:
    def test_resolves_flavor_by_matching_name(self):
        conn = MagicMock()
        with patch("app.services.nova.list_flavors") as mock_list:
            mock_list.return_value = [
                _make_flavor("cpu.1c_2g", "flavor-abc"),
                _make_flavor("cpu.2c_4g", "flavor-def"),
            ]
            result = vpn_provisioner._resolve_flavor_id(conn, "cpu.1c_2g", "")
        assert result == "flavor-abc"

    def test_override_flavor_id_skips_name_lookup(self):
        conn = MagicMock()
        with patch("app.services.nova.list_flavors") as mock_list:
            result = vpn_provisioner._resolve_flavor_id(conn, "cpu.1c_2g", "override-flavor-id")
        assert result == "override-flavor-id"
        mock_list.assert_not_called()

    def test_raises_when_flavor_name_not_found(self):
        conn = MagicMock()
        with patch("app.services.nova.list_flavors") as mock_list:
            mock_list.return_value = [_make_flavor("cpu.2c_4g", "flavor-def")]
            with pytest.raises(RuntimeError, match="cpu.1c_2g"):
                vpn_provisioner._resolve_flavor_id(conn, "cpu.1c_2g", "")

    def test_raises_when_no_flavors_exist(self):
        conn = MagicMock()
        with patch("app.services.nova.list_flavors") as mock_list:
            mock_list.return_value = []
            with pytest.raises(RuntimeError):
                vpn_provisioner._resolve_flavor_id(conn, "cpu.1c_2g", "")


# ---------------------------------------------------------------------------
# WireGuard ingress SG idempotent 생성 (_ensure_wireguard_sg)
# ---------------------------------------------------------------------------


class TestEnsureWireguardSg:
    def test_creates_new_sg_when_none_exists(self):
        conn = MagicMock()
        with (
            patch("app.services.neutron.list_security_groups", return_value=[]) as mock_list,
            patch(
                "app.services.neutron.create_security_group",
                return_value={"id": "sg-new-1"},
            ) as mock_create_sg,
            patch("app.services.neutron.create_security_group_rule") as mock_create_rule,
        ):
            sg_id = vpn_provisioner._ensure_wireguard_sg(conn, "project-1", 51820)
        assert sg_id == "sg-new-1"
        mock_list.assert_called_once()
        mock_create_sg.assert_called_once()
        mock_create_rule.assert_called_once_with(
            conn,
            "sg-new-1",
            direction="ingress",
            protocol="udp",
            port_range_min=51820,
            port_range_max=51820,
            remote_ip_prefix="0.0.0.0/0",
        )

    def test_reuses_existing_sg_by_name(self):
        conn = MagicMock()
        existing_sg = {
            "id": "sg-existing-1",
            "name": "afterglow-vpn-wireguard",
            "rules": [
                {
                    "direction": "ingress",
                    "protocol": "udp",
                    "port_range_min": 51820,
                    "port_range_max": 51820,
                    "remote_ip_prefix": "0.0.0.0/0",
                }
            ],
        }
        with (
            patch("app.services.neutron.list_security_groups", return_value=[existing_sg]),
            patch("app.services.neutron.create_security_group") as mock_create_sg,
            patch("app.services.neutron.create_security_group_rule") as mock_create_rule,
        ):
            sg_id = vpn_provisioner._ensure_wireguard_sg(conn, "project-1", 51820)
        assert sg_id == "sg-existing-1"
        mock_create_sg.assert_not_called()
        # 이미 동일 규칙이 존재하므로 중복 생성하지 않는다 (idempotent)
        mock_create_rule.assert_not_called()

    def test_adds_rule_when_sg_exists_but_rule_missing(self):
        """SG는 있지만 해당 포트 규칙이 없으면 규칙만 추가한다."""
        conn = MagicMock()
        existing_sg = {"id": "sg-existing-1", "name": "afterglow-vpn-wireguard", "rules": []}
        with (
            patch("app.services.neutron.list_security_groups", return_value=[existing_sg]),
            patch("app.services.neutron.create_security_group") as mock_create_sg,
            patch("app.services.neutron.create_security_group_rule") as mock_create_rule,
        ):
            sg_id = vpn_provisioner._ensure_wireguard_sg(conn, "project-1", 51820)
        assert sg_id == "sg-existing-1"
        mock_create_sg.assert_not_called()
        mock_create_rule.assert_called_once()


# ---------------------------------------------------------------------------
# provision_vpn_server — 전체 오케스트레이션 흐름
# ---------------------------------------------------------------------------


class TestProvisionVpnServerSuccess:
    @pytest.mark.asyncio
    async def test_full_provisioning_flow_without_fip(self):
        """floating_network_id 미설정 시 fixed IP를 endpoint로 사용, PROVISIONING 상태로 전이."""
        conn = MagicMock()
        conn.close = MagicMock()
        fake_server = MagicMock(id="vm-123")

        with (
            patch("app.services.vpn_provisioner.get_settings", return_value=_make_settings()),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch(
                "app.services.vpn_db.get_server_by_id",
                new=AsyncMock(return_value={"id": "server-1", "name": "vpn-gw-1", "listen_port": 51820}),
            ),
            patch("app.services.vpn_provisioner._resolve_flavor_id", return_value="flavor-abc"),
            patch("app.services.vpn_provisioner._ensure_wireguard_sg", return_value="sg-1"),
            patch(
                "app.services.neutron.create_port",
                return_value={"id": "port-1"},
            ) as mock_create_port,
            patch(
                "app.services.vpn_agent_auth.issue_report_token",
                new=AsyncMock(return_value="bootstrap-token-abc"),
            ),
            patch("app.services.vpn_config.render_agent_userdata", return_value="base64-userdata"),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
        ):
            conn.compute.create_server = MagicMock(return_value=fake_server)
            conn.compute.get_server = MagicMock(return_value=fake_server)

            with (
                patch("app.services.vpn_provisioner._wait_for_active", new=AsyncMock()),
                patch("app.services.vpn_provisioner._extract_fixed_ip", return_value="10.0.0.5"),
            ):
                await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        mock_create_port.assert_called_once_with(conn, "net-provider-1", "vpn-gw-1-port", ["sg-1"])
        conn.compute.create_server.assert_called_once()
        create_kwargs = conn.compute.create_server.call_args.kwargs
        assert create_kwargs["image_id"] == "img-ubuntu-1"
        assert create_kwargs["flavor_id"] == "flavor-abc"
        assert create_kwargs["networks"] == [{"port": "port-1"}]

        # 상태 전이 확인: 첫 호출은 CREATING(+server_vm_id 등), 마지막 호출은 PROVISIONING
        status_calls = mock_update_status.call_args_list
        assert status_calls[0].args[1] == "CREATING"
        assert status_calls[-1].args[1] == "PROVISIONING"
        assert status_calls[-1].kwargs["endpoint_ip"] == "10.0.0.5"
        assert status_calls[-1].kwargs["only_if_status"] == "CREATING"
        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_provisioning_flow_with_fip(self):
        """floating_network_id 설정 시 FIP를 할당하고 endpoint_ip로 사용한다."""
        conn = MagicMock()
        conn.close = MagicMock()
        fake_server = MagicMock(id="vm-123")

        with (
            patch(
                "app.services.vpn_provisioner.get_settings",
                return_value=_make_settings(vpn_floating_network_id="net-external-1"),
            ),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch(
                "app.services.vpn_db.get_server_by_id",
                new=AsyncMock(return_value={"id": "server-1", "name": "vpn-gw-1", "listen_port": 51820}),
            ),
            patch("app.services.vpn_provisioner._resolve_flavor_id", return_value="flavor-abc"),
            patch("app.services.vpn_provisioner._ensure_wireguard_sg", return_value="sg-1"),
            patch("app.services.neutron.create_port", return_value={"id": "port-1"}),
            patch(
                "app.services.vpn_agent_auth.issue_report_token",
                new=AsyncMock(return_value="bootstrap-token-abc"),
            ),
            patch("app.services.vpn_config.render_agent_userdata", return_value="base64-userdata"),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
            patch(
                "app.services.vpn_provisioner._allocate_new_fip",
                new=AsyncMock(return_value=("203.0.113.9", "fip-1")),
            ) as mock_alloc_fip,
        ):
            conn.compute.create_server = MagicMock(return_value=fake_server)
            conn.compute.get_server = MagicMock(return_value=fake_server)

            with (
                patch("app.services.vpn_provisioner._wait_for_active", new=AsyncMock()),
                patch("app.services.vpn_provisioner._extract_fixed_ip", return_value="10.0.0.5"),
            ):
                await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        mock_alloc_fip.assert_called_once_with(conn, "vm-123", "net-external-1")
        status_calls = mock_update_status.call_args_list
        assert status_calls[-1].kwargs["endpoint_ip"] == "203.0.113.9"
        assert status_calls[-1].kwargs["fip_id"] == "fip-1"


# ---------------------------------------------------------------------------
# provision_vpn_server — 실패 시 롤백
# ---------------------------------------------------------------------------


class TestProvisionVpnServerRollback:
    @pytest.mark.asyncio
    async def test_vm_boot_failure_triggers_rollback_and_error_status(self):
        """VM 생성 이후 단계(_wait_for_active)에서 예외 발생 시 리소스가 역순 롤백되고 ERROR 상태가 된다."""
        conn = MagicMock()
        conn.close = MagicMock()
        fake_server = MagicMock(id="vm-123")

        with (
            patch("app.services.vpn_provisioner.get_settings", return_value=_make_settings()),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch(
                "app.services.vpn_db.get_server_by_id",
                new=AsyncMock(return_value={"id": "server-1", "name": "vpn-gw-1", "listen_port": 51820}),
            ),
            patch("app.services.vpn_provisioner._resolve_flavor_id", return_value="flavor-abc"),
            patch("app.services.vpn_provisioner._ensure_wireguard_sg", return_value="sg-1"),
            patch("app.services.neutron.create_port", return_value={"id": "port-1"}),
            patch(
                "app.services.vpn_agent_auth.issue_report_token",
                new=AsyncMock(return_value="bootstrap-token-abc"),
            ),
            patch("app.services.vpn_config.render_agent_userdata", return_value="base64-userdata"),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
            patch("app.services.nova.delete_server") as mock_delete_server,
            patch("app.services.nova.wait_server_deleted") as mock_wait_deleted,
            patch("app.services.neutron.delete_port") as mock_delete_port,
        ):
            conn.compute.create_server = MagicMock(return_value=fake_server)

            with patch(
                "app.services.vpn_provisioner._wait_for_active",
                new=AsyncMock(side_effect=RuntimeError("VM never became ACTIVE")),
            ):
                await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        # 롤백: VM 삭제 + 포트 삭제 (SG는 idempotent 공유 리소스라 삭제하지 않음)
        mock_delete_server.assert_called_once_with(conn, "vm-123")
        mock_wait_deleted.assert_called_once()
        mock_delete_port.assert_called_once_with(conn, "port-1")

        # 최종 상태는 ERROR
        final_call = mock_update_status.call_args_list[-1]
        assert final_call.args[1] == "ERROR"
        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_provider_network_id_sets_error_without_creating_resources(self):
        conn = MagicMock()
        conn.close = MagicMock()

        with (
            patch(
                "app.services.vpn_provisioner.get_settings",
                return_value=_make_settings(vpn_provider_network_id=""),
            ),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch(
                "app.services.vpn_db.get_server_by_id",
                new=AsyncMock(return_value={"id": "server-1", "name": "vpn-gw-1", "listen_port": 51820}),
            ),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
            patch("app.services.neutron.create_port") as mock_create_port,
        ):
            await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        mock_create_port.assert_not_called()
        final_call = mock_update_status.call_args_list[-1]
        assert final_call.args[1] == "ERROR"

    @pytest.mark.asyncio
    async def test_openstack_connection_failure_sets_error_status(self):
        """keystone 연결 자체가 실패하면 리소스 생성 없이 즉시 ERROR."""
        with (
            patch("app.services.vpn_provisioner.get_settings", return_value=_make_settings()),
            patch(
                "app.services.keystone.get_admin_connection_for_project",
                side_effect=RuntimeError("keystone unreachable"),
            ),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
            patch("app.services.neutron.create_port") as mock_create_port,
        ):
            await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        mock_create_port.assert_not_called()
        final_call = mock_update_status.call_args_list[-1]
        assert final_call.args[1] == "ERROR"

    @pytest.mark.asyncio
    async def test_server_record_not_found_aborts_without_error_status(self):
        """DB에 CREATING 레코드가 없으면(경합/삭제됨) 조용히 종료 — update_server_status 호출 안 함."""
        conn = MagicMock()
        conn.close = MagicMock()
        with (
            patch("app.services.vpn_provisioner.get_settings", return_value=_make_settings()),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch("app.services.vpn_db.get_server_by_id", new=AsyncMock(return_value=None)),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
        ):
            await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")
        mock_update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_fip_allocation_failure_rolls_back_vm_and_port(self):
        """VM은 ACTIVE 됐지만 FIP 할당이 실패하면 VM/포트가 롤백된다."""
        conn = MagicMock()
        conn.close = MagicMock()
        fake_server = MagicMock(id="vm-123")

        with (
            patch(
                "app.services.vpn_provisioner.get_settings",
                return_value=_make_settings(vpn_floating_network_id="net-external-1"),
            ),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch(
                "app.services.vpn_db.get_server_by_id",
                new=AsyncMock(return_value={"id": "server-1", "name": "vpn-gw-1", "listen_port": 51820}),
            ),
            patch("app.services.vpn_provisioner._resolve_flavor_id", return_value="flavor-abc"),
            patch("app.services.vpn_provisioner._ensure_wireguard_sg", return_value="sg-1"),
            patch("app.services.neutron.create_port", return_value={"id": "port-1"}),
            patch(
                "app.services.vpn_agent_auth.issue_report_token",
                new=AsyncMock(return_value="bootstrap-token-abc"),
            ),
            patch("app.services.vpn_config.render_agent_userdata", return_value="base64-userdata"),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
            patch("app.services.nova.delete_server") as mock_delete_server,
            patch("app.services.nova.wait_server_deleted"),
            patch("app.services.neutron.delete_port") as mock_delete_port,
            patch(
                "app.services.vpn_provisioner._allocate_new_fip",
                new=AsyncMock(side_effect=RuntimeError("no floating IPs available")),
            ),
        ):
            conn.compute.create_server = MagicMock(return_value=fake_server)
            conn.compute.get_server = MagicMock(return_value=fake_server)

            with (
                patch("app.services.vpn_provisioner._wait_for_active", new=AsyncMock()),
                patch("app.services.vpn_provisioner._extract_fixed_ip", return_value="10.0.0.5"),
            ):
                await vpn_provisioner.provision_vpn_server("project-1", "server-1", "user-1", "tester")

        mock_delete_server.assert_called_once_with(conn, "vm-123")
        mock_delete_port.assert_called_once_with(conn, "port-1")
        final_call = mock_update_status.call_args_list[-1]
        assert final_call.args[1] == "ERROR"


# ---------------------------------------------------------------------------
# delete_vpn_server
# ---------------------------------------------------------------------------


class TestDeleteVpnServer:
    @pytest.mark.asyncio
    async def test_delete_cleans_up_all_resources_and_soft_deletes(self):
        conn = MagicMock()
        conn.close = MagicMock()
        server_record = {
            "server_vm_id": "vm-123",
            "fip_id": "fip-1",
            "provider_port_id": "port-1",
        }

        with (
            patch("app.services.vpn_db.get_server", new=AsyncMock(return_value=server_record)),
            patch("app.services.keystone.get_admin_connection_for_project", return_value=conn),
            patch("app.services.neutron.cleanup_instance_fips") as mock_cleanup_fips,
            patch("app.services.nova.delete_server") as mock_delete_server,
            patch("app.services.nova.wait_server_deleted") as mock_wait_deleted,
            patch("app.services.neutron.delete_port") as mock_delete_port,
            patch("app.services.vpn_agent_auth.revoke_report_token_by_server", new=AsyncMock()) as mock_revoke,
            patch("app.services.vpn_db.soft_delete_server", new=AsyncMock(return_value=True)) as mock_soft_delete,
        ):
            await vpn_provisioner.delete_vpn_server("project-1", "server-1", "user-1")

        mock_cleanup_fips.assert_called_once_with(conn, "vm-123")
        mock_delete_server.assert_called_once_with(conn, "vm-123")
        mock_wait_deleted.assert_called_once()
        mock_delete_port.assert_called_once_with(conn, "port-1")
        mock_revoke.assert_called_once_with("server-1")
        mock_soft_delete.assert_called_once_with("project-1", "server-1", "user-1", reason="사용자 요청")
        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_noop_when_server_not_found(self):
        with (
            patch("app.services.vpn_db.get_server", new=AsyncMock(return_value=None)),
            patch("app.services.keystone.get_admin_connection_for_project") as mock_conn,
        ):
            await vpn_provisioner.delete_vpn_server("project-1", "server-1", "user-1")
        mock_conn.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_connection_failure_sets_error_status(self):
        server_record = {"server_vm_id": "vm-123", "fip_id": None, "provider_port_id": "port-1"}
        with (
            patch("app.services.vpn_db.get_server", new=AsyncMock(return_value=server_record)),
            patch(
                "app.services.keystone.get_admin_connection_for_project",
                side_effect=RuntimeError("keystone unreachable"),
            ),
            patch("app.services.vpn_db.update_server_status", new=AsyncMock()) as mock_update_status,
        ):
            await vpn_provisioner.delete_vpn_server("project-1", "server-1", "user-1")
        final_call = mock_update_status.call_args_list[-1]
        assert final_call.args[1] == "ERROR"
