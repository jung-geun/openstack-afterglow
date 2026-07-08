"""cloud_init_builder 단위 테스트 — 순수 함수, mock 불필요."""

import base64

import yaml

# ---------------------------------------------------------------------------
# 헬퍼 픽스처
# ---------------------------------------------------------------------------


class _FakeRecipe:
    def __init__(self, proto="NFS", cmds=None, apt=None):
        self.share_proto = proto
        self.commands = cmds or [
            {"step": "install_py", "progress_pct": 50, "script": "echo hello\n"},
        ]
        self.apt_packages = apt or []


_TOKEN = "abcdef1234567890abcdef1234567890"

_NFS_SPEC = {"share_proto": "NFS", "export_path": "10.0.0.1:/volumes/test"}

_CEPH_SPEC = {
    "share_proto": "CEPHFS",
    "ceph_mons": "10.0.0.1:6789,10.0.0.2:6789",
    "ceph_path": "/volumes/test",
    "cephx_user": "builder-abc",
    "cephx_secret": "supersecret",
}


# ---------------------------------------------------------------------------
# render_user_data: 공통 구조 검증
# ---------------------------------------------------------------------------


def test_nfs_user_data_starts_with_cloud_config():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert out.startswith("#cloud-config\n")


def test_cephfs_user_data_starts_with_cloud_config():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)
    assert out.startswith("#cloud-config\n")


def test_nfs_includes_nfs_common_package():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert "nfs-common" in out


def test_cephfs_includes_ceph_common_package():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)
    assert "ceph-common" in out


def test_shared_builder_preinstall_packages_match_cloud_init_fallbacks():
    from app.services.cloud_init_builder import SHARED_BUILDER_IMAGE_PACKAGES, render_user_data

    nfs_out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    ceph_out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)

    assert set(SHARED_BUILDER_IMAGE_PACKAGES) == {"curl", "nfs-common", "ceph-common"}
    assert "curl" in nfs_out
    assert "nfs-common" in nfs_out
    assert "curl" in ceph_out
    assert "ceph-common" in ceph_out


def test_power_state_poweroff_present():
    from app.services.cloud_init_builder import render_user_data

    for proto, spec in [("NFS", _NFS_SPEC), ("CEPHFS", _CEPH_SPEC)]:
        out = render_user_data(_FakeRecipe(proto), spec, _TOKEN)
        assert "mode: poweroff" in out, f"poweroff not in {proto} user_data"


# ---------------------------------------------------------------------------
# sentinel 라인 검증
# ---------------------------------------------------------------------------


def test_success_sentinel_present_nfs():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert f"::AFTERGLOW::SUCCESS::{_TOKEN}" in out


def test_failure_sentinel_present_nfs():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert f"::AFTERGLOW::FAILURE::{_TOKEN}" in out


def test_success_sentinel_present_cephfs():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)
    assert f"::AFTERGLOW::SUCCESS::{_TOKEN}" in out


def test_failure_sentinel_present_cephfs():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)
    assert f"::AFTERGLOW::FAILURE::{_TOKEN}" in out


def test_sentinel_contains_unique_token():
    """다른 토큰을 쓰면 sentinel 도 달라져야 한다."""
    from app.services.cloud_init_builder import render_user_data

    token2 = "9999999999999999999999999999999a"
    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, token2)
    assert f"::AFTERGLOW::SUCCESS::{token2}" in out
    assert f"::AFTERGLOW::SUCCESS::{_TOKEN}" not in out


# ---------------------------------------------------------------------------
# tee /dev/console 확인
# ---------------------------------------------------------------------------


def test_tee_dev_console_present():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert "tee /dev/console" in out


# ---------------------------------------------------------------------------
# run-build.sh 관련
# ---------------------------------------------------------------------------


def test_run_build_sh_file_declared():
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    assert "/usr/local/bin/run-build.sh" in out


def test_run_build_sh_content_is_base64():
    """write_files 의 run-build.sh content 가 유효한 base64 이어야 한다."""
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    lines = out.splitlines()
    # content: <base64> 라인 중 하나를 찾아 디코드 가능한지 확인
    content_lines = [ln.strip() for ln in lines if ln.strip().startswith("content: ")]
    assert content_lines, "write_files content 라인이 없음"
    for cl in content_lines:
        b64_part = cl[len("content: ") :]
        decoded = base64.b64decode(b64_part)
        assert len(decoded) > 0


def test_step_progress_marker_in_build_script():
    """recipe command 의 step 이름이 run-build.sh 에 포함돼야 한다."""
    from app.services.cloud_init_builder import _render_run_build_sh

    cmds = [{"step": "install_torch", "progress_pct": 80, "script": "echo torch"}]
    script = _render_run_build_sh(cmds)
    assert ".progress_80_install_torch" in script
    assert "echo torch" in script


def test_run_build_error_trap_persists_larger_log_tail():
    from app.services.cloud_init_builder import _render_run_build_sh

    script = _render_run_build_sh([{"step": "install_numpy", "progress_pct": 80, "script": "false"}])
    assert "tail -n 1000 /var/log/cloud-init-output.log" in script
    assert "tail -n 200 /var/log/cloud-init-output.log" not in script


# ---------------------------------------------------------------------------
# NFS mount 명령
# ---------------------------------------------------------------------------


def test_nfs_mount_command_uses_nfs_type():
    from app.services.cloud_init_builder import _render_mount_lines

    lines = _render_mount_lines("NFS", {"export_path": "10.0.0.1:/path"})
    joined = " ".join(lines)
    assert "mount -t nfs" in joined
    assert "10.0.0.1:/path" in joined


def test_cephfs_mount_command_uses_ceph_type():
    from app.services.cloud_init_builder import _render_mount_lines

    lines = _render_mount_lines("CEPHFS", _CEPH_SPEC)
    joined = " ".join(lines)
    assert "mount -t ceph" in joined
    assert "builder-abc" in joined


# ---------------------------------------------------------------------------
# runcmd 블록 로직 구조
# ---------------------------------------------------------------------------


def test_runcmd_block_uses_or_rc_pattern():
    """`|| _rc=$?` 패턴으로 전체 &&체인 실패를 포착해야 한다."""
    from app.services.cloud_init_builder import _render_runcmd_body

    mount_lines = ["mkdir -p /mnt/share", "mount -t nfs 'x:/y' /mnt/share"]
    body = _render_runcmd_body(mount_lines, _TOKEN)
    assert "|| _rc=$?" in body
    assert "_rc=0" in body


def test_runcmd_success_branch_emits_success_sentinel():
    from app.services.cloud_init_builder import _render_runcmd_body

    body = _render_runcmd_body(["mount x y"], _TOKEN)
    assert f'echo "::AFTERGLOW::SUCCESS::{_TOKEN}"' in body


def test_runcmd_failure_branch_emits_failure_sentinel():
    from app.services.cloud_init_builder import _render_runcmd_body

    body = _render_runcmd_body(["mount x y"], _TOKEN)
    assert f'echo "::AFTERGLOW::FAILURE::{_TOKEN}' in body


# ---------------------------------------------------------------------------
# YAML 파싱 회귀 테스트 — &&가 YAML 앵커로 오해석되는 버그 방지
# (이전에 " \\\n  && ".join 이 literal block scalar 내 &&를 column 5에 위치시켜
#  YAML 파서가 block scalar 종료 + 앵커(&)로 오해석, empty cloud config 생성)
# ---------------------------------------------------------------------------


def test_nfs_render_output_is_valid_yaml():
    """NFS user_data 전체가 yaml.safe_load 로 파싱 가능해야 한다."""
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN)
    doc = yaml.safe_load(out)
    assert isinstance(doc, dict), "최상위가 dict 가 아님"
    assert "runcmd" in doc and doc["runcmd"], "runcmd 블록 없음"
    body = "\n".join(str(x) for x in doc["runcmd"])
    assert "mount -t nfs" in body, "NFS 마운트 명령이 runcmd 에 없음"
    assert "run-build.sh" in body, "run-build.sh 호출이 runcmd 에 없음"


def test_cephfs_render_output_is_valid_yaml():
    """CephFS user_data 전체가 yaml.safe_load 로 파싱 가능해야 한다."""
    from app.services.cloud_init_builder import render_user_data

    out = render_user_data(_FakeRecipe("CEPHFS"), _CEPH_SPEC, _TOKEN)
    doc = yaml.safe_load(out)
    assert isinstance(doc, dict), "최상위가 dict 가 아님"
    assert "runcmd" in doc and doc["runcmd"], "runcmd 블록 없음"
    body = "\n".join(str(x) for x in doc["runcmd"])
    assert "mount -t ceph" in body, "Ceph 마운트 명령이 runcmd 에 없음"
    assert "run-build.sh" in body, "run-build.sh 호출이 runcmd 에 없음"


def test_render_output_yaml_contains_power_state():
    """파싱된 doc 에 power_state.mode = poweroff 가 있어야 한다."""
    from app.services.cloud_init_builder import render_user_data

    doc = yaml.safe_load(render_user_data(_FakeRecipe("NFS"), _NFS_SPEC, _TOKEN))
    assert doc.get("power_state", {}).get("mode") == "poweroff"
