"""builder_vm 단위 테스트.

ensure_builder_vm의 멱등성·재기동·이미 ACTIVE 케이스를 검증한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_server(sid: str = "srv-1", status: str = "ACTIVE", fip: str | None = "1.2.3.4"):
    srv = MagicMock()
    srv.id = sid
    srv.status = status
    if fip:
        srv.addresses = {
            "net": [{"OS-EXT-IPS:type": "floating", "addr": fip}]
        }
    else:
        srv.addresses = {}
    return srv


def _make_settings(
    persistent_server_id: str = "",
    ssh_host: str = "",
    floating_network_id: str = "ext-net-id",
    ssh_key_path: str = "/tmp/test.key",
    ssh_user: str = "ubuntu",
    builder_image_id: str = "img-1",
    builder_flavor_id: str = "flv-1",
    builder_network_id: str = "net-1",
    default_network_id: str = "net-1",
):
    s = MagicMock()
    s.builder_persistent_server_id = persistent_server_id
    s.builder_ssh_host = ssh_host
    s.builder_floating_network_id = floating_network_id
    s.builder_ssh_key_path = ssh_key_path
    s.builder_ssh_user = ssh_user
    s.builder_image_id = builder_image_id
    s.builder_flavor_id = builder_flavor_id
    s.builder_network_id = builder_network_id
    s.default_network_id = default_network_id
    return s


# ---------------------------------------------------------------------------
# _extract_fip
# ---------------------------------------------------------------------------


def test_extract_fip_returns_floating_address():
    from app.services.builder_vm import _extract_fip

    server = _make_server(fip="1.2.3.4")
    assert _extract_fip(server) == "1.2.3.4"


def test_extract_fip_returns_none_when_no_fip():
    from app.services.builder_vm import _extract_fip

    server = _make_server(fip=None)
    assert _extract_fip(server) is None


# ---------------------------------------------------------------------------
# ensure_builder_vm — 이미 ACTIVE 상태
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_builder_vm_returns_endpoint_for_active_server():
    """ACTIVE Builder VM이 있으면 즉시 BuilderEndpoint를 반환해야 한다."""
    import app.services.builder_vm as bvm

    bvm.invalidate_cache()

    server = _make_server(sid="srv-active", status="ACTIVE", fip="1.2.3.4")
    settings = _make_settings(persistent_server_id="srv-active", ssh_host="1.2.3.4")

    svc_conn = MagicMock()

    with (
        patch("app.services.builder_vm.get_settings", return_value=settings),
        patch("app.services.builder_vm.asyncio.to_thread", new=AsyncMock(return_value=server)),
    ):
        endpoint = await bvm.ensure_builder_vm(svc_conn)

    assert endpoint.server_id == "srv-active"
    assert endpoint.host == "1.2.3.4"
    assert endpoint.username == "ubuntu"

    bvm.invalidate_cache()


@pytest.mark.asyncio
async def test_ensure_builder_vm_uses_cache_on_second_call():
    """두 번째 호출 시 캐시에서 반환해 Nova를 재조회하지 않아야 한다."""
    import app.services.builder_vm as bvm

    bvm.invalidate_cache()

    server = _make_server(sid="srv-cache", status="ACTIVE", fip="5.6.7.8")
    settings = _make_settings(persistent_server_id="srv-cache", ssh_host="5.6.7.8")

    call_count = 0

    async def _mock_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return server

    svc_conn = MagicMock()

    with (
        patch("app.services.builder_vm.get_settings", return_value=settings),
        patch("app.services.builder_vm.asyncio.to_thread", side_effect=_mock_to_thread),
    ):
        await bvm.ensure_builder_vm(svc_conn)
        await bvm.ensure_builder_vm(svc_conn)

    # 두 번째 호출은 캐시 히트 — Nova 재조회 없음
    assert call_count == 1

    bvm.invalidate_cache()


# ---------------------------------------------------------------------------
# ensure_builder_vm — SHUTOFF 재기동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_builder_vm_restarts_shutoff_server():
    """SHUTOFF 상태 서버는 start_server를 호출해 재기동해야 한다."""
    import app.services.builder_vm as bvm

    bvm.invalidate_cache()

    shutoff_server = _make_server(sid="srv-shut", status="SHUTOFF", fip="1.2.3.4")
    active_server = _make_server(sid="srv-shut", status="ACTIVE", fip="1.2.3.4")
    settings = _make_settings(persistent_server_id="srv-shut", ssh_host="1.2.3.4")

    call_seq = iter([shutoff_server, None, active_server, active_server])

    async def _mock_to_thread(fn, *args, **kwargs):
        return next(call_seq, active_server)

    svc_conn = MagicMock()

    with (
        patch("app.services.builder_vm.get_settings", return_value=settings),
        patch("app.services.builder_vm.asyncio.to_thread", side_effect=_mock_to_thread),
        patch("app.services.builder_vm._wait_for_active", new=AsyncMock()),
    ):
        endpoint = await bvm.ensure_builder_vm(svc_conn)

    assert endpoint.server_id == "srv-shut"
    assert endpoint.host == "1.2.3.4"

    bvm.invalidate_cache()


# ---------------------------------------------------------------------------
# _build_ssh_command
# ---------------------------------------------------------------------------


def test_build_ssh_command_contains_mount_and_install():
    """생성된 SSH 명령에 mount 명령과 install 스크립트 실행이 포함돼야 한다."""
    from app.services.library_builder import _build_ssh_command

    cmd = _build_ssh_command(
        ceph_mons="10.0.0.1",
        share_path="/volumes/_nogroup/abc",
        cephx_user="union-builder-python311",
        cephx_secret="AQTEST==",
        install_script="echo installing",
    )
    assert "mount -t ceph" in cmd
    assert "union-builder-python311" in cmd
    assert ".union_build_complete" in cmd
    assert "base64 -d" in cmd


def test_build_ssh_command_encodes_secret_as_base64():
    """cephx_secret이 base64로 인코딩되어 명령에 포함돼야 한다."""
    import base64

    from app.services.library_builder import _build_ssh_command

    secret = "AQ+specialchars==\nwith newline"
    cmd = _build_ssh_command(
        ceph_mons="mon", share_path="/path", cephx_user="user",
        cephx_secret=secret, install_script="echo ok",
    )
    expected_b64 = base64.b64encode(secret.encode()).decode()
    assert expected_b64 in cmd
    # 원본 시크릿이 그대로 노출되지 않아야 한다
    assert secret not in cmd
