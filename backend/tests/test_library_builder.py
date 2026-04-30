"""library_builder 단위 테스트.

A2: 빌드 완료 후 probe VM 마운트 검증 — _verify_layer_accessible / _generate_probe_cloudinit
A3: 백그라운드 빌드 워커 — asyncio.create_task 기반 비동기 빌드 검증
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _generate_probe_cloudinit
# ---------------------------------------------------------------------------


def test_probe_cloudinit_contains_mount_command():
    """생성된 cloud-init에 CephFS 마운트 명령이 포함돼야 한다."""
    from app.services.library_builder import _generate_probe_cloudinit

    script = _generate_probe_cloudinit(
        ceph_monitors="10.0.0.1:6789",
        share_path="/volumes/_nogroup/abc123",
        cephx_user="union-probe-torch",
        cephx_key="AQTEST==",
    )
    assert "mount -t ceph 10.0.0.1:6789:/volumes/_nogroup/abc123" in script
    assert "union-probe-torch" in script


def test_probe_cloudinit_checks_marker_file():
    """생성된 cloud-init이 .union_build_complete 존재를 확인해야 한다."""
    from app.services.library_builder import _generate_probe_cloudinit

    script = _generate_probe_cloudinit("mon", "/path", "user", "key")
    assert ".union_build_complete" in script
    assert "VERIFY_OK" in script
    assert "VERIFY_FAIL" in script


def test_probe_cloudinit_uses_ro_option():
    """RO 마운트 옵션이 포함돼야 한다."""
    from app.services.library_builder import _generate_probe_cloudinit

    script = _generate_probe_cloudinit("mon", "/path", "user", "key")
    assert ",ro" in script


# ---------------------------------------------------------------------------
# _verify_layer_accessible
# ---------------------------------------------------------------------------


def _make_probe_server(sid: str = "probe-srv-1", status: str = "SHUTOFF"):
    srv = MagicMock()
    srv.id = sid
    srv.status = status
    return srv


@pytest.mark.asyncio
async def test_verify_layer_accessible_returns_true_on_verify_ok():
    """probe VM 콘솔에 VERIFY_OK가 있으면 True 반환."""
    from app.services.library_builder import _verify_layer_accessible

    conn = MagicMock()
    conn.compute.create_server.return_value = _make_probe_server()
    conn.compute.get_server.return_value = _make_probe_server(status="SHUTOFF")
    conn.compute.get_server_console_output.return_value = {"output": "[union-probe] VERIFY_OK\n"}

    with (
        patch(
            "app.services.library_builder.manila.create_access_rule",
            return_value={"access_key": "AQTEST==", "access_id": "rule-1"},
        ),
        patch(
            "app.services.library_builder.manila.get_export_locations",
            return_value=["10.0.0.1:6789:/volumes/_nogroup/abc"],
        ),
        patch("app.services.library_builder.manila.list_access_rules", return_value=[]),
        patch("app.services.library_builder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await _verify_layer_accessible(conn, "share-1", "torch", "img-1", "flv-1", "net-1")

    assert result is True


@pytest.mark.asyncio
async def test_verify_layer_accessible_returns_false_on_verify_fail():
    """probe VM 콘솔에 VERIFY_FAIL이 있으면 False 반환."""
    from app.services.library_builder import _verify_layer_accessible

    conn = MagicMock()
    conn.compute.create_server.return_value = _make_probe_server()
    conn.compute.get_server.return_value = _make_probe_server(status="SHUTOFF")
    conn.compute.get_server_console_output.return_value = {"output": "[union-probe] VERIFY_FAIL: marker not found\n"}

    with (
        patch(
            "app.services.library_builder.manila.create_access_rule",
            return_value={"access_key": "AQTEST==", "access_id": "rule-1"},
        ),
        patch(
            "app.services.library_builder.manila.get_export_locations",
            return_value=["10.0.0.1:6789:/volumes/_nogroup/abc"],
        ),
        patch("app.services.library_builder.manila.list_access_rules", return_value=[]),
        patch("app.services.library_builder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await _verify_layer_accessible(conn, "share-1", "torch", "img-1", "flv-1", "net-1")

    assert result is False


@pytest.mark.asyncio
async def test_verify_layer_accessible_cleans_up_probe_rule():
    """검증 완료 후 probe access rule이 정리돼야 한다."""
    from app.services.library_builder import _verify_layer_accessible

    conn = MagicMock()
    conn.compute.create_server.return_value = _make_probe_server()
    conn.compute.get_server.return_value = _make_probe_server(status="SHUTOFF")
    conn.compute.get_server_console_output.return_value = {"output": "[union-probe] VERIFY_OK"}

    mock_revoke = MagicMock()
    with (
        patch(
            "app.services.library_builder.manila.create_access_rule",
            return_value={"access_key": "AQTEST==", "access_id": "rule-1"},
        ),
        patch(
            "app.services.library_builder.manila.get_export_locations",
            return_value=["10.0.0.1:6789:/volumes/_nogroup/abc"],
        ),
        patch(
            "app.services.library_builder.manila.list_access_rules",
            return_value=[{"id": "rule-1", "access_to": "union-probe-python311"}],
        ),
        patch("app.services.library_builder.manila.revoke_access_rule", mock_revoke),
        patch("app.services.library_builder.asyncio.sleep", new_callable=AsyncMock),
    ):
        await _verify_layer_accessible(conn, "share-1", "python311", "img-1", "flv-1", "net-1")

    mock_revoke.assert_called_once()


@pytest.mark.asyncio
async def test_verify_layer_accessible_returns_false_on_vm_error():
    """probe VM이 ERROR 상태면 False 반환."""
    from app.services.library_builder import _verify_layer_accessible

    conn = MagicMock()
    conn.compute.create_server.return_value = _make_probe_server()
    conn.compute.get_server.return_value = _make_probe_server(status="ERROR")

    with (
        patch(
            "app.services.library_builder.manila.create_access_rule",
            return_value={"access_key": "AQTEST==", "access_id": "rule-1"},
        ),
        patch(
            "app.services.library_builder.manila.get_export_locations",
            return_value=["10.0.0.1:6789:/vol"],
        ),
        patch("app.services.library_builder.manila.list_access_rules", return_value=[]),
        patch("app.services.library_builder.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await _verify_layer_accessible(conn, "share-1", "torch", "img-1", "flv-1", "net-1")

    assert result is False


# ---------------------------------------------------------------------------
# A3: start_build — asyncio.create_task 백그라운드 워커
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_build_creates_background_task():
    """start_build()는 asyncio.create_task로 모니터링 코루틴을 백그라운드에서 실행한다."""
    from app.services import library_builder

    captured_tasks = []

    def _fake_create_task(coro):
        captured_tasks.append(coro)
        # 코루틴을 닫아 "never awaited" 경고 방지
        coro.close()
        return MagicMock()

    mock_file_storage = MagicMock()
    mock_file_storage.id = "share-build-1"

    mock_server = MagicMock()
    mock_server.id = "builder-vm-1"

    with (
        patch("app.services.library_builder.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.library_builder.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread,
        patch("app.services.library_builder.asyncio.create_task", side_effect=_fake_create_task),
        patch("app.services.library_builder.get_settings") as mock_settings,
        patch("app.services.library_builder._active_builds", {}),
    ):
        settings = MagicMock()
        settings.builder_image_id = "img-ubuntu"
        settings.builder_flavor_id = "flv-small"
        settings.builder_network_id = "net-mgmt"
        settings.default_network_id = "net-mgmt"
        settings.os_manila_share_network_id = "snet-1"
        settings.os_manila_share_type = "cephfstype"
        mock_settings.return_value = settings

        # to_thread 호출 순서 (start_build에서 모두 asyncio.to_thread로 호출됨):
        #   1. get_service_project_connection → conn
        #   2. create_file_storage → mock_file_storage
        #   3. create_access_rule → dict
        #   4. get_export_locations → list
        #   5. _create_builder_vm → mock_server
        mock_conn = MagicMock()
        mock_to_thread.side_effect = [
            mock_conn,  # get_service_project_connection
            mock_file_storage,  # create_file_storage
            {"access_key": "AQTEST==", "access_id": "r1"},  # create_access_rule
            ["10.0.0.1:6789:/vol/lib"],  # get_export_locations
            mock_server,  # _create_builder_vm
        ]

        result = await library_builder.start_build("python311")

    assert result["status"] == "building"
    assert len(captured_tasks) == 1, "create_task가 정확히 한 번 호출돼야 한다"


@pytest.mark.asyncio
async def test_start_build_rejects_duplicate_library():
    """동일 라이브러리에 대해 빌드가 진행 중이면 RuntimeError를 발생시킨다."""
    from app.services import library_builder

    fake_active = {"python311": {"status": "building"}}

    with patch("app.services.library_builder._active_builds", fake_active):
        with pytest.raises(RuntimeError, match="이미 빌드 중인"):
            await library_builder.start_build("python311")
