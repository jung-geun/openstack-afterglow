"""OpenTofu runner 서비스 단위 테스트."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.services.tofu_runner import (
    TofuApplyError,
    TofuDestroyError,
    TofuNotFound,
    _env_from_conn,
    _tofu_bin,
)

# ---------------------------------------------------------------------------
# _tofu_bin
# ---------------------------------------------------------------------------


def test_tofu_bin_raises_when_not_found():
    with patch("shutil.which", return_value=None):
        with pytest.raises(TofuNotFound):
            _tofu_bin()


def test_tofu_bin_returns_path():
    with patch("shutil.which", return_value="/usr/local/bin/tofu"):
        assert _tofu_bin() == "/usr/local/bin/tofu"


# ---------------------------------------------------------------------------
# _env_from_conn
# ---------------------------------------------------------------------------


def test_env_from_conn_maps_auth():
    conn = MagicMock()
    conn.auth = {
        "auth_url": "https://keystone:5000/v3",
        "username": "admin",
        "password": "secret",
        "project_id": "proj-1",
        "user_domain_name": "Default",
    }
    env = _env_from_conn(conn)
    assert env["OS_AUTH_URL"] == "https://keystone:5000/v3"
    assert env["OS_USERNAME"] == "admin"
    assert env["OS_PASSWORD"] == "secret"
    assert env["TF_IN_AUTOMATION"] == "1"


def test_env_from_conn_skips_empty_values():
    conn = MagicMock()
    conn.auth = {"auth_url": "https://ks:5000/v3", "username": "", "password": "pw"}
    env = _env_from_conn(conn)
    assert "OS_USERNAME" not in env
    assert env["OS_AUTH_URL"] == "https://ks:5000/v3"


# ---------------------------------------------------------------------------
# apply (subprocess mock)
# ---------------------------------------------------------------------------


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


FAKE_OUTPUTS_JSON = json.dumps(
    {
        "server_id": {"value": "srv-tofu-1"},
        "internal_ip": {"value": "10.0.1.5"},
        "ssh_host": {"value": "10.0.1.5"},
        "share_id": {"value": "share-tofu-nfs"},
        "fip_id": {"value": ""},
        "access_key": {"value": ""},
    }
)


@pytest.mark.asyncio
async def test_apply_returns_workdir_and_outputs(tmp_path):
    """정상 경로: init → apply → output 순서로 tofu 를 호출하고 outputs 를 파싱한다."""
    module_dir = tmp_path / "builder_smoke"
    module_dir.mkdir()
    (module_dir / "main.tf").write_text("# placeholder")

    conn = MagicMock()
    conn.auth = {"auth_url": "https://ks/v3", "username": "u", "password": "p"}

    side_effects = [
        _completed(0),  # init
        _completed(0),  # apply
        _completed(0, stdout=FAKE_OUTPUTS_JSON),  # output
    ]

    with (
        patch("shutil.which", return_value="/usr/local/bin/tofu"),
        patch("subprocess.run", side_effect=side_effects),
        patch("app.services.tofu_runner._TOFU_MODULES_DIR", tmp_path),
    ):
        from app.services import tofu_runner

        workdir, outputs = await tofu_runner.apply("builder_smoke", {"vm_name": "test"}, conn)

    assert outputs["server_id"] == "srv-tofu-1"
    assert outputs["internal_ip"] == "10.0.1.5"
    assert workdir.exists()
    import shutil

    shutil.rmtree(workdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_apply_raises_on_init_failure(tmp_path):
    module_dir = tmp_path / "builder_smoke"
    module_dir.mkdir()
    (module_dir / "main.tf").write_text("")

    conn = MagicMock()
    conn.auth = {"auth_url": "https://ks/v3"}

    with (
        patch("shutil.which", return_value="/usr/local/bin/tofu"),
        patch("subprocess.run", return_value=_completed(1, stderr="provider error")),
        patch("app.services.tofu_runner._TOFU_MODULES_DIR", tmp_path),
    ):
        from app.services import tofu_runner

        with pytest.raises(TofuApplyError, match="init 실패"):
            await tofu_runner.apply("builder_smoke", {}, conn)


@pytest.mark.asyncio
async def test_destroy_removes_workdir(tmp_path):
    """destroy 완료 후 workdir 가 삭제되어야 한다."""
    workdir = tmp_path / "run-123"
    workdir.mkdir()
    (workdir / "terraform.tfstate").write_text("{}")

    conn = MagicMock()
    conn.auth = {"auth_url": "https://ks/v3"}

    with (
        patch("shutil.which", return_value="/usr/local/bin/tofu"),
        patch("subprocess.run", return_value=_completed(0)),
    ):
        from app.services import tofu_runner

        await tofu_runner.destroy(workdir, conn)

    assert not workdir.exists()


@pytest.mark.asyncio
async def test_destroy_raises_on_failure(tmp_path):
    """destroy 실패 시 TofuDestroyError 를 발생시키고 workdir 는 정리된다."""
    workdir = tmp_path / "run-fail"
    workdir.mkdir()

    conn = MagicMock()
    conn.auth = {"auth_url": "https://ks/v3"}

    with (
        patch("shutil.which", return_value="/usr/local/bin/tofu"),
        patch("subprocess.run", return_value=_completed(1, stderr="state lock")),
    ):
        from app.services import tofu_runner

        with pytest.raises(TofuDestroyError):
            await tofu_runner.destroy(workdir, conn)

    assert not workdir.exists()
