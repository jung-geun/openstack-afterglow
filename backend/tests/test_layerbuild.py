"""scripts/layerbuild.py 단위 테스트.

scripts/는 backend 패키지가 아니므로 sys.path에 직접 추가.
GNU tar 의존 테스트는 macOS BSD tar 환경에서 자동 skip.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/layerbuild.py import
SCRIPTS_DIR = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import layerbuild  # noqa: E402

# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------


def _has_gnu_tar() -> bool:
    """GNU tar (--sort=name 지원) 존재 여부."""
    try:
        result = subprocess.run(
            ["tar", "--sort=name", "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


needs_gnu_tar = pytest.mark.skipif(
    not _has_gnu_tar(),
    reason="GNU tar (--sort=name) 미설치 — macOS BSD tar 환경에서 자동 skip",
)


@pytest.fixture
def isolated_layer_store(tmp_path, monkeypatch):
    """LAYER_STORE_RW를 tmp_path로 격리. 테스트 간 상태 누설 방지."""
    monkeypatch.setattr(layerbuild, "LAYER_STORE_RW", tmp_path)
    monkeypatch.setattr(layerbuild, "_STATE_FILE", tmp_path / ".layerbuild_state.json")
    monkeypatch.setattr(layerbuild, "_WORK_DIR", tmp_path / "build-work")
    return tmp_path


def _normalize_dir(path: Path) -> None:
    """결정성 보장: 모든 파일/디렉토리에 명시적 mode + epoch mtime 설정."""
    for entry in path.rglob("*"):
        if entry.is_file():
            os.chmod(entry, 0o644)
        elif entry.is_dir():
            os.chmod(entry, 0o755)
        os.utime(entry, (0, 0))
    os.chmod(path, 0o755)
    os.utime(path, (0, 0))


# ---------------------------------------------------------------------------
# 4.1  Pure 헬퍼
# ---------------------------------------------------------------------------


def test_load_save_clear_state_roundtrip(isolated_layer_store):
    """state 파일 save/load/clear 라운드트립."""
    assert layerbuild._load_state() == {}
    payload = {"build_id": "abc", "name": "test", "version": "1.0"}
    layerbuild._save_state(payload)
    assert layerbuild._load_state() == payload
    layerbuild._clear_state()
    assert layerbuild._load_state() == {}


@needs_gnu_tar
def test_compute_layer_hash_deterministic(tmp_path):
    """동일 콘텐츠 디렉토리 두 개 → 동일 hash (정규화된 fixture)."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    for d in (a, b):
        d.mkdir()
        (d / "file.txt").write_text("hello world")
        (d / "sub").mkdir()
        (d / "sub" / "inner.txt").write_text("inner content")
        _normalize_dir(d)

    h1 = layerbuild._compute_layer_hash(a)
    h2 = layerbuild._compute_layer_hash(b)
    assert h1 == h2
    assert h1.startswith("sha256:")
    assert len(h1) == len("sha256:") + 64


@needs_gnu_tar
def test_compute_layer_hash_detects_content_change(tmp_path):
    """파일 한 글자 바꾸면 hash 변경."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    for d, content in [(a, "hello"), (b, "world")]:
        d.mkdir()
        (d / "file.txt").write_text(content)
        _normalize_dir(d)

    h1 = layerbuild._compute_layer_hash(a)
    h2 = layerbuild._compute_layer_hash(b)
    assert h1 != h2


@needs_gnu_tar
def test_compute_layer_hash_empty_dir(tmp_path):
    """빈 디렉토리도 결정적 hash 반환."""
    a = tmp_path / "a"
    a.mkdir()
    _normalize_dir(a)
    h = layerbuild._compute_layer_hash(a)
    assert h.startswith("sha256:")


def test_compute_layer_hash_dry_run_returns_placeholder(tmp_path):
    """dry-run에서는 GNU tar 없이도 placeholder hash 반환."""
    a = tmp_path / "a"
    a.mkdir()
    h = layerbuild._compute_layer_hash(a, dry_run=True)
    assert h == layerbuild._PLACEHOLDER_HASH


# ---------------------------------------------------------------------------
# 4.2  argparse 파싱
# ---------------------------------------------------------------------------


def test_argparse_init_requires_version():
    """init은 --version 필수."""
    parser = layerbuild._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["init", "test-name"])


def test_argparse_dry_run_flag():
    """글로벌 --dry-run 플래그가 args.dry_run으로 파싱."""
    parser = layerbuild._build_parser()
    args = parser.parse_args(["--dry-run", "init", "test", "--version", "1.0"])
    assert args.dry_run is True
    assert args.cmd == "init"
    assert args.name == "test"
    assert args.version == "1.0"


def test_argparse_resume_api_subcommand():
    """resume-api 서브커맨드는 layer_id 인자를 받음."""
    parser = layerbuild._build_parser()
    args = parser.parse_args(["resume-api", "sha256:abc"])
    assert args.cmd == "resume-api"
    assert args.layer_id == "sha256:abc"
    assert args.func == layerbuild.cmd_resume_api


# ---------------------------------------------------------------------------
# 4.3  cmd_init (mock subprocess + urllib)
# ---------------------------------------------------------------------------


def _init_args(name="test", version="1.0", parent=None, ubuntu_base=None, dry_run=False):
    """argparse.Namespace 사용 — MagicMock의 'parent'는 내부 속성과 충돌."""
    return argparse.Namespace(
        cmd="init",
        name=name,
        version=version,
        parent=parent,
        ubuntu_base=ubuntu_base,
        dry_run=dry_run,
    )


def test_cmd_init_no_parent_creates_state(isolated_layer_store):
    """parent 없을 때 bind mount + state 파일 생성."""
    with patch.object(layerbuild, "_run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_init(_init_args(name="base", version="1.0"))

    assert layerbuild._STATE_FILE.exists()
    state = json.loads(layerbuild._STATE_FILE.read_text())
    assert state["name"] == "base"
    assert state["version"] == "1.0"
    assert state["has_overlay"] is False

    # mount --bind 호출 확인
    call_cmd = mock_run.call_args.args[0]
    assert call_cmd[0] == "mount"
    assert call_cmd[1] == "--bind"


def test_cmd_init_with_parent_calls_api_for_chain(isolated_layer_store, monkeypatch):
    """parent 지정 시 _api_get으로 조상 체인 조회 + lowerdir에 포함."""
    monkeypatch.setattr(layerbuild, "API_URL", "http://api")
    monkeypatch.setattr(layerbuild, "API_TOKEN", "token")
    parent_hash = "sha256:" + ("a" * 64)
    base_hash = "sha256:" + ("b" * 64)
    # 부모/조상 diff 디렉토리 사전 생성
    for h in (parent_hash, base_hash):
        (isolated_layer_store / f"sha256-{h.removeprefix('sha256:')}" / "diff").mkdir(parents=True)

    with (
        patch.object(layerbuild, "_run") as mock_run,
        patch.object(
            layerbuild,
            "_api_get",
            return_value={"layers": [{"id": base_hash}, {"id": parent_hash}]},
        ),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_init(_init_args(parent=parent_hash))

    # mount overlay 호출 검증 — lowerdir에 두 path 포함
    call_cmd = mock_run.call_args.args[0]
    assert call_cmd[0] == "mount"
    assert call_cmd[1] == "-t"
    assert call_cmd[2] == "overlay"
    mount_opts = call_cmd[5]
    assert "lowerdir=" in mount_opts
    assert f"sha256-{base_hash.removeprefix('sha256:')}/diff" in mount_opts
    assert f"sha256-{parent_hash.removeprefix('sha256:')}/diff" in mount_opts


def test_cmd_init_existing_state_aborts(isolated_layer_store):
    """state 이미 있으면 SystemExit(1)."""
    layerbuild._save_state({"build_id": "preexisting"})
    with pytest.raises(SystemExit) as exc:
        layerbuild.cmd_init(_init_args())
    assert exc.value.code == 1


def test_cmd_init_dry_run_no_mount_no_state(isolated_layer_store):
    """dry-run에서는 subprocess 미호출 + state 파일 미생성 + 디렉토리 미생성."""
    with patch.object(layerbuild, "_run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_init(_init_args(dry_run=True))

    # _run은 호출되지만 (트레이스 출력) 실제 subprocess는 dry-run 분기로 미실행 — 호출 자체는 1번 (mount --bind)
    assert mock_run.called
    # state 파일은 작성되지 않음
    assert not layerbuild._STATE_FILE.exists()
    # 작업 디렉토리도 생성되지 않음
    assert not (isolated_layer_store / "build-work").exists()


def test_cmd_init_with_parent_no_api_env_fails_clearly(isolated_layer_store, monkeypatch):
    """parent 지정 + API 환경변수 미설정 → 명확한 에러."""
    monkeypatch.setattr(layerbuild, "API_URL", "")
    monkeypatch.setattr(layerbuild, "API_TOKEN", "")
    with pytest.raises(SystemExit) as exc:
        layerbuild.cmd_init(_init_args(parent="sha256:" + "a" * 64))
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# 4.4  cmd_seal
# ---------------------------------------------------------------------------


def test_cmd_seal_without_state_aborts(isolated_layer_store):
    """state 없으면 exit 1."""
    args = MagicMock(dry_run=False)
    with pytest.raises(SystemExit) as exc:
        layerbuild.cmd_seal(args)
    assert exc.value.code == 1


def test_cmd_seal_calls_api_post_register_then_seal(isolated_layer_store, monkeypatch):
    """API POST /api/union/layers + /api/union/layers/{id}/seal 순서 검증."""
    monkeypatch.setattr(layerbuild, "API_URL", "http://api")
    monkeypatch.setattr(layerbuild, "API_TOKEN", "token")

    upper = isolated_layer_store / "build-work" / "b1" / "upper"
    upper.mkdir(parents=True)
    (upper / "file.txt").write_text("payload")
    layerbuild._save_state(
        {
            "build_id": "b1",
            "name": "test-layer",
            "version": "1.0",
            "parent_id": None,
            "ubuntu_base": "ubuntu:22.04",
            "work": str(isolated_layer_store / "build-work" / "b1"),
            "upper": str(upper),
            "merged": str(isolated_layer_store / "build-work" / "b1" / "merged"),
        }
    )

    fixed_hash = "sha256:" + ("c" * 64)
    api_calls: list[tuple[str, dict]] = []

    def _fake_post(path, data, *, dry_run=False):
        api_calls.append((path, data))
        return {}

    args = MagicMock(dry_run=False)
    with (
        patch.object(layerbuild, "_run") as mock_run,
        patch.object(layerbuild, "_compute_layer_hash", return_value=fixed_hash),
        patch.object(layerbuild, "_api_post", side_effect=_fake_post),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_seal(args)

    assert len(api_calls) == 2
    assert api_calls[0][0] == "/api/union/layers"
    assert api_calls[0][1]["content_hash"] == fixed_hash
    assert api_calls[0][1]["name"] == "test-layer"
    assert api_calls[1][0] == f"/api/union/layers/{fixed_hash}/seal"


def test_cmd_seal_api_failure_writes_api_pending_marker(isolated_layer_store, monkeypatch):
    """POST 예외 발생 시 .api_pending 마커 기록 + content_hash 포함."""
    monkeypatch.setattr(layerbuild, "API_URL", "http://api")
    monkeypatch.setattr(layerbuild, "API_TOKEN", "token")

    upper = isolated_layer_store / "build-work" / "b2" / "upper"
    upper.mkdir(parents=True)
    (upper / "f.txt").write_text("x")
    layerbuild._save_state(
        {
            "build_id": "b2",
            "name": "fail-layer",
            "version": "1.0",
            "parent_id": None,
            "ubuntu_base": None,
            "work": str(isolated_layer_store / "build-work" / "b2"),
            "upper": str(upper),
            "merged": str(isolated_layer_store / "build-work" / "b2" / "merged"),
        }
    )

    fixed_hash = "sha256:" + ("d" * 64)
    args = MagicMock(dry_run=False)
    with (
        patch.object(layerbuild, "_run") as mock_run,
        patch.object(layerbuild, "_compute_layer_hash", return_value=fixed_hash),
        patch.object(layerbuild, "_api_post", side_effect=RuntimeError("boom")),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_seal(args)

    marker = isolated_layer_store / f"sha256-{fixed_hash.removeprefix('sha256:')}" / ".api_pending"
    assert marker.is_file()
    payload = json.loads(marker.read_text())
    assert payload["content_hash"] == fixed_hash
    assert payload["name"] == "fail-layer"


def test_cmd_seal_dry_run_outputs_command_trace(isolated_layer_store):
    """dry-run에서 umount/chmod 미실행 + placeholder hash 반환."""
    args = MagicMock(dry_run=True)
    captured_commands: list[list[str]] = []

    def _capturing_run(cmd, *, dry_run=False, capture=False, check=False):
        captured_commands.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

    with patch.object(layerbuild, "_run", side_effect=_capturing_run):
        layerbuild.cmd_seal(args)

    # 명령 트레이스에 umount, chmod, chattr 포함됨
    cmds = [c[0] for c in captured_commands]
    assert "umount" in cmds
    assert "chmod" in cmds
    assert "chattr" in cmds


# ---------------------------------------------------------------------------
# 4.5  cmd_abort
# ---------------------------------------------------------------------------


def test_cmd_abort_without_state_returns_quietly(isolated_layer_store):
    """state 없으면 그냥 종료 (예외 없음)."""
    args = MagicMock()
    layerbuild.cmd_abort(args)  # 예외 없음


def test_cmd_abort_unmounts_and_clears(isolated_layer_store):
    """umount 호출 + work 디렉토리 rmtree + state 클리어."""
    work = isolated_layer_store / "build-work" / "b3"
    (work / "upper").mkdir(parents=True)
    layerbuild._save_state(
        {
            "build_id": "b3",
            "work": str(work),
            "merged": str(work / "merged"),
            "upper": str(work / "upper"),
        }
    )

    args = MagicMock()
    with patch.object(layerbuild, "_run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        layerbuild.cmd_abort(args)

    # umount 호출됨
    assert mock_run.call_args.args[0][0] == "umount"
    # work 디렉토리 정리
    assert not work.exists()
    # state 클리어
    assert layerbuild._load_state() == {}


# ---------------------------------------------------------------------------
# 4.6  cmd_resume_api
# ---------------------------------------------------------------------------


def test_resume_api_reads_pending_and_posts(isolated_layer_store, monkeypatch):
    """`.api_pending` 마커 읽고 POST 두 번 → 마커 삭제."""
    monkeypatch.setattr(layerbuild, "API_URL", "http://api")
    monkeypatch.setattr(layerbuild, "API_TOKEN", "token")

    layer_hash = "sha256:" + ("e" * 64)
    dest = isolated_layer_store / f"sha256-{layer_hash.removeprefix('sha256:')}"
    dest.mkdir()
    payload = {
        "name": "resumed",
        "version": "1.0",
        "parent_id": None,
        "ubuntu_base": None,
        "build_recipe": {},
        "installed_packages": {},
        "content_hash": layer_hash,
        "size_bytes": 0,
        "file_count": 0,
    }
    (dest / ".api_pending").write_text(json.dumps(payload))

    api_calls = []

    def _fake_post(path, data, *, dry_run=False):
        api_calls.append((path, data))
        return {}

    args = MagicMock(layer_id=layer_hash)
    with patch.object(layerbuild, "_api_post", side_effect=_fake_post):
        layerbuild.cmd_resume_api(args)

    assert len(api_calls) == 2
    assert api_calls[0][0] == "/api/union/layers"
    assert api_calls[1][0] == f"/api/union/layers/{layer_hash}/seal"
    assert not (dest / ".api_pending").exists()


def test_resume_api_missing_marker_exits(isolated_layer_store):
    """마커 없으면 exit 1."""
    args = MagicMock(layer_id="sha256:" + ("f" * 64))
    with pytest.raises(SystemExit) as exc:
        layerbuild.cmd_resume_api(args)
    assert exc.value.code == 1
