"""임시 Builder VM Manila 마운트 서비스 및 smoke-mount 엔드포인트 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_settings(**kwargs) -> MagicMock:
    s = MagicMock()
    s.os_manila_nfs_share_type = kwargs.get("os_manila_nfs_share_type", "nfstype")
    s.os_manila_share_type = kwargs.get("os_manila_share_type", "cephfstype")
    s.os_manila_share_network_id = kwargs.get("os_manila_share_network_id", "net-manila")
    return s


def _make_storage(share_id: str = "share-abc") -> MagicMock:
    s = MagicMock()
    s.id = share_id
    return s


def _make_vm(
    server_id: str = "srv-xyz",
    host: str = "5.5.5.5",
    internal_ip: str = "10.0.0.7",
) -> MagicMock:
    from app.services.builder_vm import EphemeralBuilderVM

    return EphemeralBuilderVM(
        server_id=server_id,
        host=host,
        username="ubuntu",
        key_path="/tmp/k.key",
        internal_ip=internal_ip,
        fip_id="fip-xyz",
    )


# ---------------------------------------------------------------------------
# create_builder_share
# ---------------------------------------------------------------------------


class TestCreateBuilderShare:
    @pytest.mark.asyncio
    async def test_nfs_uses_nfs_share_type_and_network(self):
        """NFS share는 os_manila_nfs_share_type과 share_network_id를 사용한다."""
        svc_conn = MagicMock()
        storage = _make_storage("share-nfs-1")

        with (
            patch(
                "app.services.ephemeral_mount.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "app.services.ephemeral_mount.manila.create_file_storage",
                return_value=storage,
            ) as mock_create,
        ):
            result = await __import__(
                "app.services.ephemeral_mount", fromlist=["create_builder_share"]
            ).create_builder_share(svc_conn, "test-nfs", 5, "NFS")

        assert result == "share-nfs-1"
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["share_type"] == "nfstype"
        assert call_kwargs.kwargs["share_network_id"] == "net-manila"
        assert call_kwargs.kwargs["share_proto"] == "NFS"

    @pytest.mark.asyncio
    async def test_cephfs_skips_share_network(self):
        """CephFS share는 share_network_id를 빈 문자열로 넘긴다."""
        svc_conn = MagicMock()
        storage = _make_storage("share-ceph-1")

        with (
            patch(
                "app.services.ephemeral_mount.get_settings",
                return_value=_make_settings(),
            ),
            patch(
                "app.services.ephemeral_mount.manila.create_file_storage",
                return_value=storage,
            ) as mock_create,
        ):
            from app.services.ephemeral_mount import create_builder_share

            result = await create_builder_share(svc_conn, "test-cephfs", 10, "CEPHFS")

        assert result == "share-ceph-1"
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["share_type"] == "cephfstype"
        assert call_kwargs.kwargs["share_network_id"] == ""
        assert call_kwargs.kwargs["share_proto"] == "CEPHFS"


# ---------------------------------------------------------------------------
# add_vm_access_rule
# ---------------------------------------------------------------------------


class TestAddVmAccessRule:
    @pytest.mark.asyncio
    async def test_nfs_creates_ip_access_rule(self):
        """NFS는 access_type='ip', access_to=VM IP로 rule을 생성한다."""
        svc_conn = MagicMock()
        mock_rule = {"access_id": "rule-nfs-1", "access_key": "", "access_to": "10.0.0.7", "access_level": "rw"}

        with patch(
            "app.services.ephemeral_mount.manila.create_access_rule",
            return_value=mock_rule,
        ) as mock_create:
            from app.services.ephemeral_mount import add_vm_access_rule

            result = await add_vm_access_rule(svc_conn, "share-abc", "10.0.0.7", "NFS")

        assert result["access_id"] == "rule-nfs-1"
        _, pos_args, kw = mock_create.mock_calls[0]
        # positional: conn, share_id, access_to, access_level, access_type
        assert pos_args[2] == "10.0.0.7"  # access_to = VM IP
        assert pos_args[3] == "rw"
        assert pos_args[4] == "ip"

    @pytest.mark.asyncio
    async def test_cephfs_creates_cephx_access_rule(self):
        """CephFS는 access_type='cephx', access_to=cephx_user로 rule을 생성한다."""
        svc_conn = MagicMock()
        mock_rule = {
            "access_id": "rule-ceph-1",
            "access_key": "AQBsecret==",
            "access_to": "builder-shareabc",
            "access_level": "rw",
        }

        with patch(
            "app.services.ephemeral_mount.manila.create_access_rule",
            return_value=mock_rule,
        ) as mock_create:
            from app.services.ephemeral_mount import add_vm_access_rule

            result = await add_vm_access_rule(
                svc_conn, "shareabc1234", "10.0.0.7", "CEPHFS", cephx_user="my-builder"
            )

        assert result["access_id"] == "rule-ceph-1"
        assert result["access_key"] == "AQBsecret=="
        _, pos_args, _ = mock_create.mock_calls[0]
        assert pos_args[2] == "my-builder"  # 지정한 cephx_user
        assert pos_args[4] == "cephx"

    @pytest.mark.asyncio
    async def test_cephfs_generates_default_cephx_user(self):
        """cephx_user 미지정 시 share_id 앞 8자로 자동 생성한다."""
        svc_conn = MagicMock()
        mock_rule = {
            "access_id": "rule-auto",
            "access_key": "AQsecret==",
            "access_to": "builder-share123",
            "access_level": "rw",
        }

        with patch(
            "app.services.ephemeral_mount.manila.create_access_rule",
            return_value=mock_rule,
        ) as mock_create:
            from app.services.ephemeral_mount import add_vm_access_rule

            await add_vm_access_rule(svc_conn, "share1234abcd", "10.0.0.7", "CEPHFS")

        _, pos_args, _ = mock_create.mock_calls[0]
        assert pos_args[2] == "builder-share123"  # share_id[:8] = "share123"


# ---------------------------------------------------------------------------
# build_mount_command
# ---------------------------------------------------------------------------


class TestBuildMountCommand:
    @pytest.mark.asyncio
    async def test_nfs_command_contains_export_path(self):
        """NFS 마운트 명령에 export_location이 포함된다."""
        svc_conn = MagicMock()

        with patch(
            "app.services.ephemeral_mount.manila.get_export_locations",
            return_value=["10.10.10.5:/shares/share-abc"],
        ):
            from app.services.ephemeral_mount import build_mount_command

            cmd = await build_mount_command(svc_conn, "share-abc", "NFS", {})

        assert "mount -t nfs" in cmd
        assert "10.10.10.5:/shares/share-abc" in cmd
        assert "/mnt/lib-output" in cmd
        assert "sudo" in cmd

    @pytest.mark.asyncio
    async def test_cephfs_command_contains_user_and_secret(self):
        """CephFS 마운트 명령에 cephx user와 base64 secret이 포함된다."""
        svc_conn = MagicMock()
        access_rule = {"access_to": "builder-x", "access_key": "mysecret"}

        with patch(
            "app.services.ephemeral_mount.manila.get_export_locations",
            return_value=["10.10.10.1,10.10.10.2:/volumes/vol1"],
        ):
            from app.services.ephemeral_mount import build_mount_command

            cmd = await build_mount_command(svc_conn, "share-abc", "CEPHFS", access_rule)

        assert "mount -t ceph" in cmd
        assert "builder-x" in cmd
        assert "secretfile" in cmd
        import base64

        assert base64.b64encode(b"mysecret").decode() in cmd

    @pytest.mark.asyncio
    async def test_raises_when_no_export_locations(self):
        """export_location이 없으면 RuntimeError."""
        svc_conn = MagicMock()

        with patch(
            "app.services.ephemeral_mount.manila.get_export_locations",
            return_value=[],
        ):
            from app.services.ephemeral_mount import build_mount_command

            with pytest.raises(RuntimeError, match="export location"):
                await build_mount_command(svc_conn, "share-abc", "NFS", {})


# ---------------------------------------------------------------------------
# verify_mount_via_ssh
# ---------------------------------------------------------------------------


class TestVerifyMountViaSsh:
    @pytest.mark.asyncio
    async def test_returns_mounted_true_on_success(self):
        """mount + verify 모두 성공 시 mounted=True."""
        vm = _make_vm()

        with patch(
            "app.services.ephemeral_mount.run_command",
            new_callable=AsyncMock,
            side_effect=[
                (0, "", ""),                           # mount 성공
                (0, "Filesystem ...\nMOUNT_OK", ""),  # verify 성공
                (0, "", ""),                           # umount
            ],
        ):
            from app.services.ephemeral_mount import verify_mount_via_ssh

            result = await verify_mount_via_ssh(vm, "sudo mount ...\n")

        assert result["mounted"] is True
        assert "MOUNT_OK" in result["df_output"]
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_returns_mounted_false_on_mount_failure(self):
        """mount 실패 시 mounted=False, error 포함."""
        vm = _make_vm()

        with patch(
            "app.services.ephemeral_mount.run_command",
            new_callable=AsyncMock,
            return_value=(1, "", "mount: bad option"),
        ):
            from app.services.ephemeral_mount import verify_mount_via_ssh

            result = await verify_mount_via_ssh(vm, "sudo mount ...\n")

        assert result["mounted"] is False
        assert "mount 실패" in result["error"]

    @pytest.mark.asyncio
    async def test_umount_called_even_on_verify_failure(self):
        """검증 실패해도 umount는 항상 호출된다."""
        vm = _make_vm()
        mock_run = AsyncMock(
            side_effect=[
                (0, "", ""),      # mount 성공
                (1, "", "err"),   # verify 실패
                (0, "", ""),      # umount
            ]
        )

        with patch("app.services.ephemeral_mount.run_command", mock_run):
            from app.services.ephemeral_mount import verify_mount_via_ssh

            result = await verify_mount_via_ssh(vm, "sudo mount ...\n")

        assert result["mounted"] is False
        assert mock_run.call_count == 3  # mount + verify + umount


# ---------------------------------------------------------------------------
# smoke-mount 엔드포인트
# ---------------------------------------------------------------------------


class TestSmokeMountEndpoint:
    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self, non_admin_client):
        """일반 사용자 → 403."""
        resp = await non_admin_client.post(
            "/api/admin/libraries/builder-vm/_smoke-mount",
            json={"share_proto": "NFS"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_proto_returns_400(self, admin_client):
        """잘못된 share_proto → 400."""
        with patch(
            "app.api.identity.admin_libraries.get_service_project_connection",
            return_value=MagicMock(),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/builder-vm/_smoke-mount",
                json={"share_proto": "S3"},
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_nfs_smoke_mount_ok(self, admin_client):
        """NFS 정상 흐름: status=ok 반환."""
        vm = _make_vm()

        with (
            patch(
                "app.api.identity.admin_libraries.get_service_project_connection",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.builder_vm.create_ephemeral_vm",
                new_callable=AsyncMock,
                return_value=vm,
            ),
            patch(
                "app.services.ephemeral_mount.create_builder_share",
                new_callable=AsyncMock,
                return_value="share-smoke",
            ),
            patch(
                "app.services.ephemeral_mount.add_vm_access_rule",
                new_callable=AsyncMock,
                return_value={"access_id": "rule-1", "access_key": "", "access_to": "10.0.0.7", "access_level": "rw"},
            ),
            patch(
                "app.services.ephemeral_mount.build_mount_command",
                new_callable=AsyncMock,
                return_value="sudo mount ...\n",
            ),
            patch(
                "app.services.ephemeral_mount.verify_mount_via_ssh",
                new_callable=AsyncMock,
                return_value={"mounted": True, "df_output": "Filesystem 1.0G", "error": None},
            ),
            patch("app.services.builder_vm.delete_ephemeral_vm", new_callable=AsyncMock),
            patch("app.services.manila.revoke_access_rule"),
            patch("app.services.manila.delete_file_storage"),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/builder-vm/_smoke-mount",
                json={"share_proto": "NFS", "size_gb": 1},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["share_proto"] == "NFS"
        assert data["server_id"] == "srv-xyz"

    @pytest.mark.asyncio
    async def test_cleans_up_on_mount_failure(self, admin_client):
        """마운트 실패 시 share·VM이 정리되고 500이 반환된다."""
        vm = _make_vm()
        mock_delete_vm = AsyncMock()

        with (
            patch(
                "app.api.identity.admin_libraries.get_service_project_connection",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.builder_vm.create_ephemeral_vm",
                new_callable=AsyncMock,
                return_value=vm,
            ),
            patch(
                "app.services.ephemeral_mount.create_builder_share",
                new_callable=AsyncMock,
                return_value="share-fail",
            ),
            patch(
                "app.services.ephemeral_mount.add_vm_access_rule",
                new_callable=AsyncMock,
                return_value={"access_id": "rule-fail", "access_key": "", "access_to": "10.0.0.7", "access_level": "rw"},
            ),
            patch(
                "app.services.ephemeral_mount.build_mount_command",
                new_callable=AsyncMock,
                return_value="sudo mount ...\n",
            ),
            patch(
                "app.services.ephemeral_mount.verify_mount_via_ssh",
                new_callable=AsyncMock,
                return_value={"mounted": False, "df_output": "", "error": "mount: no route to host"},
            ),
            patch("app.services.builder_vm.delete_ephemeral_vm", mock_delete_vm),
            patch("app.services.manila.revoke_access_rule"),
            patch("app.services.manila.delete_file_storage"),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/builder-vm/_smoke-mount",
                json={"share_proto": "NFS"},
            )

        assert resp.status_code == 500
        mock_delete_vm.assert_awaited_once()
