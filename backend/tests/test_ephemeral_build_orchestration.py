"""ephemeral_build 오케스트레이터 단위 테스트.

OpenStack/Manila/Neutron/Nova 는 모두 mock 처리.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------

_TOKEN = "aaaa1111bbbb2222cccc3333dddd4444"
_SUCCESS_LINE = f"::AFTERGLOW::SUCCESS::{_TOKEN}"
_FAILURE_LINE = f"::AFTERGLOW::FAILURE::{_TOKEN}::rc=1"


class _FakeRecipe:
    library_id = "python311"
    share_proto = "NFS"
    share_size_gb = 5
    base_image_id = None
    commands = [{"step": "install_py", "progress_pct": 50, "script": "echo hi"}]
    apt_packages = []


def _make_settings():
    s = MagicMock()
    s.builder_image_id = "img-001"
    s.builder_flavor_id = "flv-001"
    s.builder_network_id = "net-001"
    s.builder_ssh_key_path = "/tmp/key"
    s.os_manila_nfs_share_type = "nfs-type"
    s.os_manila_share_network_id = "sn-001"
    return s


def _make_conn():
    conn = MagicMock()
    server = MagicMock()
    server.id = "server-001"
    conn.compute.create_server.return_value = server
    # SHUTOFF on first poll
    shutoff_server = MagicMock()
    shutoff_server.status = "SHUTOFF"
    conn.compute.get_server.return_value = shutoff_server
    return conn


# ---------------------------------------------------------------------------
# 공통 패치 헬퍼
# ---------------------------------------------------------------------------


def _common_patches(token=_TOKEN, console_output=None):
    """run_ephemeral_build 에 필요한 공통 의존성 mock 집합을 반환한다."""
    if console_output is None:
        console_output = _SUCCESS_LINE

    patches = {
        "get_settings": patch(
            "app.services.ephemeral_build.get_settings",
            return_value=_make_settings(),
        ),
        "get_service_project_connection": patch(
            "app.services.ephemeral_build.get_service_project_connection",
            return_value=_make_conn(),
        ),
        "library_recipes": patch(
            "app.services.ephemeral_build.library_recipes",
        ),
        "ephemeral_mount": patch(
            "app.services.ephemeral_build.ephemeral_mount",
        ),
        "neutron": patch(
            "app.services.ephemeral_build.neutron",
        ),
        "nova": patch(
            "app.services.ephemeral_build.nova",
        ),
        "manila": patch(
            "app.services.ephemeral_build.manila",
        ),
        "_ensure_ephemeral_keypair": patch(
            "app.services.ephemeral_build._ensure_ephemeral_keypair",
            new=AsyncMock(return_value="keypair-name"),
        ),
        "render_user_data": patch(
            "app.services.ephemeral_build.render_user_data",
            return_value="#cloud-config\n",
        ),
        "_update_db": patch(
            "app.services.ephemeral_build._update_db",
            new=AsyncMock(),
        ),
        "uuid_hex": patch(
            "app.services.ephemeral_build.uuid",
        ),
    }
    return patches


# ---------------------------------------------------------------------------
# 성공 경로 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ephemeral_build_success_calls_delete_server():
    """성공 경로에서 server 삭제가 호출돼야 한다."""
    from app.services.ephemeral_build import run_ephemeral_build

    with (
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build.get_service_project_connection", return_value=_make_conn()) as conn_mock,
        patch("app.services.ephemeral_build.library_recipes") as lr,
        patch("app.services.ephemeral_build.ephemeral_mount") as em,
        patch("app.services.ephemeral_build.neutron") as neu,
        patch("app.services.ephemeral_build.nova") as nov,
        patch("app.services.ephemeral_build.manila") as man,
        patch("app.services.ephemeral_build._ensure_ephemeral_keypair", new=AsyncMock(return_value="kp")),
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=AsyncMock()),
        patch("app.services.ephemeral_build._wait_for_shutoff", new=AsyncMock()),
    ):
        # Setup
        lr.get_recipe = AsyncMock(return_value=_FakeRecipe())
        em.create_builder_share = AsyncMock(return_value="share-001")
        neu.create_port = MagicMock(return_value={"id": "port-001", "fixed_ip": "10.0.0.5"})
        neu.delete_port = MagicMock()
        man.ensure_nfs_access_rule = MagicMock(return_value={"access_id": "rule-001"})
        man.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        man.revoke_access_rule = MagicMock()
        man.update_share_metadata = MagicMock()
        man.set_share_public = MagicMock()
        man.list_access_rules = MagicMock(return_value=[])
        man.create_access_rule = MagicMock(return_value={"access_id": "ro-rule", "access_key": ""})
        nov.get_console_output = MagicMock(return_value=_SUCCESS_LINE)

        conn = _make_conn()
        conn_mock.return_value = conn

        await run_ephemeral_build("python311", 1)

        conn.compute.delete_server.assert_called_once()


@pytest.mark.asyncio
async def test_run_ephemeral_build_success_calls_delete_port():
    """성공 경로에서 port 삭제가 호출돼야 한다."""
    from app.services.ephemeral_build import run_ephemeral_build

    with (
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build.get_service_project_connection"),
        patch("app.services.ephemeral_build.library_recipes") as lr,
        patch("app.services.ephemeral_build.ephemeral_mount") as em,
        patch("app.services.ephemeral_build.neutron") as neu,
        patch("app.services.ephemeral_build.nova") as nov,
        patch("app.services.ephemeral_build.manila") as man,
        patch("app.services.ephemeral_build._ensure_ephemeral_keypair", new=AsyncMock(return_value="kp")),
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=AsyncMock()),
        patch("app.services.ephemeral_build._wait_for_shutoff", new=AsyncMock()),
    ):
        lr.get_recipe = AsyncMock(return_value=_FakeRecipe())
        em.create_builder_share = AsyncMock(return_value="share-001")
        neu.create_port = MagicMock(return_value={"id": "port-001", "fixed_ip": "10.0.0.5"})
        neu.delete_port = MagicMock()
        man.ensure_nfs_access_rule = MagicMock(return_value={"access_id": "rule-001"})
        man.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        man.revoke_access_rule = MagicMock()
        man.update_share_metadata = MagicMock()
        man.set_share_public = MagicMock()
        man.list_access_rules = MagicMock(return_value=[])
        man.create_access_rule = MagicMock(return_value={"access_id": "ro-rule", "access_key": ""})
        nov.get_console_output = MagicMock(return_value=_SUCCESS_LINE)

        await run_ephemeral_build("python311", 1)

        neu.delete_port.assert_called_once()


# ---------------------------------------------------------------------------
# 실패 sentinel 경로 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ephemeral_build_failure_sentinel_marks_error():
    """FAILURE sentinel 감지 시 DB error 상태 갱신 및 cleanup 호출."""
    from app.services.ephemeral_build import run_ephemeral_build

    update_calls = []

    async def _capture_update(build_id, **kwargs):
        update_calls.append(kwargs)

    with (
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build.get_service_project_connection"),
        patch("app.services.ephemeral_build.library_recipes") as lr,
        patch("app.services.ephemeral_build.ephemeral_mount") as em,
        patch("app.services.ephemeral_build.neutron") as neu,
        patch("app.services.ephemeral_build.nova") as nov,
        patch("app.services.ephemeral_build.manila") as man,
        patch("app.services.ephemeral_build._ensure_ephemeral_keypair", new=AsyncMock(return_value="kp")),
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=_capture_update),
        patch("app.services.ephemeral_build._wait_for_shutoff", new=AsyncMock()),
    ):
        lr.get_recipe = AsyncMock(return_value=_FakeRecipe())
        em.create_builder_share = AsyncMock(return_value="share-001")
        neu.create_port = MagicMock(return_value={"id": "port-001", "fixed_ip": "10.0.0.5"})
        neu.delete_port = MagicMock()
        man.ensure_nfs_access_rule = MagicMock(return_value={"access_id": "rule-001"})
        man.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        man.revoke_access_rule = MagicMock()
        man.update_share_metadata = MagicMock()
        man.set_share_public = MagicMock()
        man.list_access_rules = MagicMock(return_value=[])
        nov.get_console_output = MagicMock(return_value=_FAILURE_LINE)

        await run_ephemeral_build("python311", 1)

    # At least one call should set status=error
    error_calls = [c for c in update_calls if c.get("status") == "error"]
    assert error_calls, f"status=error 호출 없음. 실제 호출: {update_calls}"
    # port cleanup must still happen
    neu.delete_port.assert_called_once()


# ---------------------------------------------------------------------------
# sentinel 부재 → indeterminate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ephemeral_build_no_sentinel_marks_indeterminate():
    """sentinel 이 없으면 cloud_init_status=indeterminate 로 마킹돼야 한다."""
    from app.services.ephemeral_build import run_ephemeral_build

    update_calls = []

    async def _capture_update(build_id, **kwargs):
        update_calls.append(kwargs)

    with (
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build.get_service_project_connection"),
        patch("app.services.ephemeral_build.library_recipes") as lr,
        patch("app.services.ephemeral_build.ephemeral_mount") as em,
        patch("app.services.ephemeral_build.neutron") as neu,
        patch("app.services.ephemeral_build.nova") as nov,
        patch("app.services.ephemeral_build.manila") as man,
        patch("app.services.ephemeral_build._ensure_ephemeral_keypair", new=AsyncMock(return_value="kp")),
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=_capture_update),
        patch("app.services.ephemeral_build._wait_for_shutoff", new=AsyncMock()),
    ):
        lr.get_recipe = AsyncMock(return_value=_FakeRecipe())
        em.create_builder_share = AsyncMock(return_value="share-001")
        neu.create_port = MagicMock(return_value={"id": "port-001", "fixed_ip": "10.0.0.5"})
        neu.delete_port = MagicMock()
        man.ensure_nfs_access_rule = MagicMock(return_value={"access_id": "rule-001"})
        man.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        man.update_share_metadata = MagicMock()
        man.list_access_rules = MagicMock(return_value=[])
        nov.get_console_output = MagicMock(return_value="no sentinel here at all")

        await run_ephemeral_build("python311", 1)

    indeterminate_calls = [c for c in update_calls if c.get("cloud_init_status") == "indeterminate"]
    assert indeterminate_calls, f"indeterminate 마킹 없음. 실제 호출: {update_calls}"
    neu.delete_port.assert_called_once()


# ---------------------------------------------------------------------------
# port 생성 → rule 생성 → server 생성 순서
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_port_created_before_access_rule():
    """Neutron port 생성이 Manila access rule 생성보다 먼저 호출돼야 한다."""
    call_order = []

    from app.services.ephemeral_build import run_ephemeral_build

    with (
        patch("app.services.ephemeral_build.get_settings", return_value=_make_settings()),
        patch("app.services.ephemeral_build.get_service_project_connection"),
        patch("app.services.ephemeral_build.library_recipes") as lr,
        patch("app.services.ephemeral_build.ephemeral_mount") as em,
        patch("app.services.ephemeral_build.neutron") as neu,
        patch("app.services.ephemeral_build.nova") as nov,
        patch("app.services.ephemeral_build.manila") as man,
        patch("app.services.ephemeral_build._ensure_ephemeral_keypair", new=AsyncMock(return_value="kp")),
        patch("app.services.ephemeral_build.render_user_data", return_value="#cloud-config\n"),
        patch("app.services.ephemeral_build._update_db", new=AsyncMock()),
        patch("app.services.ephemeral_build._wait_for_shutoff", new=AsyncMock()),
    ):
        def _create_port(*a, **kw):
            call_order.append("create_port")
            return {"id": "port-001", "fixed_ip": "10.0.0.5"}

        def _ensure_rule(*a, **kw):
            call_order.append("ensure_nfs_access_rule")
            return {"access_id": "rule-001"}

        lr.get_recipe = AsyncMock(return_value=_FakeRecipe())
        em.create_builder_share = AsyncMock(return_value="share-001")
        neu.create_port = MagicMock(side_effect=_create_port)
        neu.delete_port = MagicMock()
        man.ensure_nfs_access_rule = MagicMock(side_effect=_ensure_rule)
        man.get_export_locations = MagicMock(return_value=["10.0.0.1:/path"])
        man.revoke_access_rule = MagicMock()
        man.update_share_metadata = MagicMock()
        man.set_share_public = MagicMock()
        man.list_access_rules = MagicMock(return_value=[])
        man.create_access_rule = MagicMock(return_value={"access_id": "ro-rule", "access_key": ""})
        nov.get_console_output = MagicMock(return_value=_SUCCESS_LINE)

        await run_ephemeral_build("python311", 1)

    assert call_order.index("create_port") < call_order.index("ensure_nfs_access_rule")
