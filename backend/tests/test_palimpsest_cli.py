"""`scripts/palimpsest.py` — 로컬 빌드·업로드 CLI 단위 테스트.

이 CLI 는 **사용자 머신**에서 돈다. 백엔드는 사용자 머신에 접근할 수 없으므로 베이스 이미지를
받고 빌드해서 올리는 일은 여기서 한다.

고정하는 계약:
- 표준 라이브러리만 쓴다 (사용자가 별도 의존성을 설치하지 않아도 되게)
- `pull` 은 받은 뒤 digest 를 **재검증**하고, 불일치면 파일을 지운다
- `pack` 은 백엔드 빌드 경로와 **같은 mksquashfs 옵션**을 쓴다
- 셸을 거치지 않는다 (인자 리스트)
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path

import pytest

_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "palimpsest.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("palimpsest_cli", _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


# ---------------------------------------------------------------------------
# 의존성 / 안전성
# ---------------------------------------------------------------------------


def test_cli_uses_only_standard_library():
    """사용자가 pip install 없이 바로 쓸 수 있어야 한다."""
    tree = ast.parse(_CLI_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    stdlib = {
        "argparse",
        "hashlib",
        "json",
        "hmac",
        "os",
        "shutil",
        "subprocess",
        "sys",
        "urllib",
        "pathlib",
        "time",
        "__future__",
    }
    assert imported <= stdlib, f"표준 라이브러리 밖 의존성: {sorted(imported - stdlib)}"


def test_cli_never_invokes_a_shell():
    source = _CLI_PATH.read_text(encoding="utf-8")

    assert "shell=True" not in source
    assert "os.system" not in source


# ---------------------------------------------------------------------------
# digest
# ---------------------------------------------------------------------------


def test_digest_file_matches_sha256_and_size(tmp_path):
    payload = b"palimpsest layer bytes" * 100
    path = tmp_path / "layer.sqsh"
    path.write_bytes(payload)

    digest, size = cli.digest_file(path)

    assert digest == "sha256:" + hashlib.sha256(payload).hexdigest()
    assert size == len(payload)


def test_digest_file_streams_without_loading_whole_file(tmp_path):
    # 레이어는 GB 단위가 될 수 있다 — 통째로 읽으면 안 된다
    source = _CLI_PATH.read_text(encoding="utf-8")

    assert "read_bytes()" not in source.split("def digest_file")[1].split("def ")[0]


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------


def test_pack_command_matches_backend_build_options(tmp_path):
    source = tmp_path / "rootfs"
    source.mkdir()

    command = cli.build_mksquashfs_command(source, tmp_path / "out.sqsh")

    # 백엔드 recipe_blocks.py 와 같은 옵션이어야 허브의 레이어가 어디서 만들어졌든 성질이 같다
    assert command[0] == "mksquashfs"
    assert "-comp" in command and command[command.index("-comp") + 1] == "zstd"
    assert "-Xcompression-level" in command
    assert "-noappend" in command
    assert "-no-exports" in command


def test_pack_command_rejects_non_directory(tmp_path):
    missing = tmp_path / "nope"

    with pytest.raises(cli.PalimpsestCliError):
        cli.build_mksquashfs_command(missing, tmp_path / "out.sqsh")


# ---------------------------------------------------------------------------
# 환경 검증
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["PALIMPSEST_URL", "PALIMPSEST_TOKEN"])
def test_missing_environment_is_reported_actionably(monkeypatch, missing):
    monkeypatch.setenv("PALIMPSEST_URL", "https://example.com")
    monkeypatch.setenv("PALIMPSEST_TOKEN", "token")
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(cli.PalimpsestCliError, match=missing):
        cli._base_url() if missing == "PALIMPSEST_URL" else cli._token()


def test_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("PALIMPSEST_URL", "https://example.com/")

    assert cli._base_url() == "https://example.com"


# ---------------------------------------------------------------------------
# 표시
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(512, "512 B"), (2048, "2.0 KiB"), (5 * 1024**2, "5.0 MiB"), (3 * 1024**3, "3.0 GiB")],
)
def test_format_size(value, expected):
    assert cli.format_size(value) == expected


# ---------------------------------------------------------------------------
# CLI 표면
# ---------------------------------------------------------------------------


def test_parser_exposes_the_local_build_workflow():
    parser = cli.build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, __import__("argparse")._SubParsersAction)
    )

    # 로컬에서 이미지를 받아 → 빌드해 → 허브에 올리는 흐름이 전부 있어야 한다
    assert {"images", "layers", "pull", "pack", "push", "bundle"} <= set(subparsers.choices)


def test_push_accepts_cloud_image_metadata():
    args = cli.build_parser().parse_args(
        [
            "push",
            "base.qcow2",
            "--name",
            "ubuntu-2404",
            "--kind",
            "cloud-image",
            "--disk-format",
            "qcow2",
            "--arch",
            "x86_64",
            "--os-variant",
            "ubuntu24.04",
        ]
    )

    assert args.kind == "cloud-image"
    assert args.disk_format == "qcow2"
    assert args.arch == "x86_64"


def test_push_accepts_layer_parentage_and_base_image():
    digest = "sha256:" + "a" * 64
    args = cli.build_parser().parse_args(
        ["push", "layer.sqsh", "--name", "torch", "--parent", digest, "--base-image", digest]
    )

    assert args.parent == digest
    assert args.base_image == digest


def test_push_refuses_to_claim_success_for_unregistered_blob(tmp_path, monkeypatch):
    """blob 은 있는데 허브에 등록되지 않은 상태를 '등록 완료' 로 보고하면 안 된다.

    단축 경로에는 업로드 세션이 없어 메타를 붙일 방법이 없다 — 조용히 성공한 척하는 대신
    무슨 일이 있었는지 알려야 한다.
    """
    payload = tmp_path / "layer.sqsh"
    payload.write_bytes(b"already in the store")
    monkeypatch.setattr(
        cli, "_json_request", lambda *a, **k: {"completed": True, "registered": False, "already_present": True}
    )

    args = cli.build_parser().parse_args(["push", str(payload), "--name", "mylayer"])

    with pytest.raises(cli.PalimpsestCliError, match="등록되어 있지 않습니다"):
        cli.cmd_push(args)


def test_push_skips_upload_when_content_is_already_registered(tmp_path, monkeypatch, capsys):
    payload = tmp_path / "layer.sqsh"
    payload.write_bytes(b"already registered")
    calls: list[tuple] = []

    def _fake(method, path, body=None):
        calls.append((method, path))
        return {"completed": True, "registered": True, "already_present": True}

    monkeypatch.setattr(cli, "_json_request", _fake)
    args = cli.build_parser().parse_args(["push", str(payload), "--name", "mylayer"])

    assert cli.cmd_push(args) == 0
    # 업로드 세션을 시작하는 POST 한 번뿐 — PATCH/PUT 이 없어야 한다
    assert calls == [("POST", "/uploads")]
    assert "업로드를 생략" in capsys.readouterr().out


def test_bundle_can_request_base_image():
    args = cli.build_parser().parse_args(["bundle", "sha256:" + "a" * 64, "-o", "out.tar", "--include-base-image"])

    assert args.include_base_image is True
    assert args.refs == ["sha256:" + "a" * 64]


def test_parser_supports_nested_image_commands():
    parser = cli.build_parser()
    subparsers = next(action for action in parser._actions if action.dest == "command")
    assert "image" in subparsers.choices

    # image list
    args_list = parser.parse_args(["image", "list"])
    assert args_list.command == "image"
    assert args_list.subcommand == "list"
    assert args_list.func == cli.cmd_image_list

    # image pull
    args_pull = parser.parse_args(["image", "pull", "img-123", "--format", "qcow2", "-o", "out.qcow2"])
    assert args_pull.command == "image"
    assert args_pull.subcommand == "pull"
    assert args_pull.image_id == "img-123"
    assert args_pull.format == "qcow2"
    assert args_pull.output == "out.qcow2"
    assert args_pull.func == cli.cmd_image_pull

    # All six formats supported in --format
    for fmt in ["raw", "qcow2", "vmdk", "vdi", "vhd", "vhdx"]:
        parsed = parser.parse_args(["image", "pull", "img-123", "--format", fmt, "-o", "out"])
        assert parsed.format == fmt

    # Unsupported format rejected by parser
    with pytest.raises(SystemExit):
        parser.parse_args(["image", "pull", "img-123", "--format", "iso", "-o", "out"])


def test_cmd_image_list_glance_output(monkeypatch, capsys):
    rows = [
        {
            "id": "img-001",
            "name": "ubuntu-24.04",
            "disk_format": "qcow2",
            "status": "active",
            "size": 104857600,
        }
    ]
    monkeypatch.setattr(cli, "_json_request", lambda method, path: rows)
    args = cli.build_parser().parse_args(["image", "list"])
    ret = cli.cmd_image_list(args)

    assert ret == 0
    out = capsys.readouterr().out
    assert "img-001" in out
    assert "ubuntu-24.04" in out
    assert "qcow2" in out
    assert "active" in out
    assert "100.0 MiB" in out

    # Empty list
    monkeypatch.setattr(cli, "_json_request", lambda method, path: [])
    ret_empty = cli.cmd_image_list(args)
    assert ret_empty == 0
    assert "베이스 이미지가 없습니다" in capsys.readouterr().out


def test_cmd_image_pull_refuses_existing_output_and_part_before_enqueue(tmp_path, monkeypatch):
    out_file = tmp_path / "out.qcow2"
    part_file = tmp_path / "out.qcow2.part"
    called = False

    def _mock_json(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(cli, "_json_request", _mock_json)

    # Existing final output file
    out_file.write_bytes(b"existing")
    args = cli.build_parser().parse_args(["image", "pull", "img-123", "--format", "qcow2", "-o", str(out_file)])
    with pytest.raises(cli.PalimpsestCliError, match="출력 파일이 이미 존재합니다"):
        cli.cmd_image_pull(args)
    assert not called

    # Existing .part file
    out_file.unlink()
    part_file.write_bytes(b"existing part")
    with pytest.raises(cli.PalimpsestCliError, match="임시 파일이 이미 존재합니다"):
        cli.cmd_image_pull(args)
    assert not called


def test_cmd_image_pull_queued_to_complete_polling_and_atomic_publication(tmp_path, monkeypatch, capsys):
    out_file = tmp_path / "downloaded.qcow2"
    part_file = tmp_path / "downloaded.qcow2.part"
    payload = b"converted-qcow2-image-bytes-content"
    digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"

    responses = [
        {"id": "job-777"},  # POST /image-exports
        {"status": "queued", "progress_pct": 0},  # GET job status 1
        {"status": "converting", "progress_pct": 50},  # GET job status 2
        {  # GET job status 3
            "status": "complete",
            "progress_pct": 100,
            "blob_digest": digest,
            "download_path": "/api/v1/palimpsest/hub/image-exports/job-777/blob",
        },
    ]

    def _mock_json_request(method, path, body=None):
        return responses.pop(0)

    class _MockStreamResp:
        def read(self, chunk_size=None):
            return b""

        def __enter__(self):
            import io

            return io.BytesIO(payload)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(cli, "_json_request", _mock_json_request)
    monkeypatch.setattr(cli, "_request", lambda method, path: _MockStreamResp())
    monkeypatch.setattr("time.sleep", lambda secs: None)

    args = cli.build_parser().parse_args(["image", "pull", "img-777", "--format", "qcow2", "-o", str(out_file)])
    ret = cli.cmd_image_pull(args)

    assert ret == 0
    assert out_file.is_file()
    assert out_file.read_bytes() == payload
    assert not part_file.exists()

    captured = capsys.readouterr()
    err = captured.err
    assert "상태: queued (0%)" in err
    assert "상태: converting (50%)" in err
    assert "상태: complete (100%)" in err

    stdout = captured.out
    assert str(out_file) in stdout
    assert digest in stdout


def test_cmd_image_pull_terminal_error(tmp_path, monkeypatch):
    out_file = tmp_path / "err.qcow2"
    part_file = tmp_path / "err.qcow2.part"

    responses = [
        {"id": "job-888"},
        {"status": "error", "error_code": "conversion_failed", "error_message": "qemu-img convert exited with 1"},
    ]

    monkeypatch.setattr(cli, "_json_request", lambda method, path, body=None: responses.pop(0))
    monkeypatch.setattr("time.sleep", lambda secs: None)

    args = cli.build_parser().parse_args(["image", "pull", "img-888", "--format", "qcow2", "-o", str(out_file)])
    with pytest.raises(cli.PalimpsestCliError, match="내보내기 작업 실패: qemu-img convert exited with 1"):
        cli.cmd_image_pull(args)

    assert not out_file.exists()
    assert not part_file.exists()


def test_cmd_image_pull_digest_mismatch_and_owned_part_cleanup(tmp_path, monkeypatch):
    out_file = tmp_path / "mismatch.qcow2"
    part_file = tmp_path / "mismatch.qcow2.part"
    payload = b"some bytes"
    expected_digest = "sha256:" + "0" * 64

    responses = [
        {"id": "job-999"},
        {
            "status": "complete",
            "progress_pct": 100,
            "blob_digest": expected_digest,
            "download_path": "/api/v1/palimpsest/hub/image-exports/job-999/blob",
        },
    ]

    class _MockStreamResp:
        def __enter__(self):
            import io

            return io.BytesIO(payload)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(cli, "_json_request", lambda method, path, body=None: responses.pop(0))
    monkeypatch.setattr(cli, "_request", lambda method, path: _MockStreamResp())
    monkeypatch.setattr("time.sleep", lambda secs: None)

    args = cli.build_parser().parse_args(["image", "pull", "img-999", "--format", "qcow2", "-o", str(out_file)])
    with pytest.raises(cli.PalimpsestCliError, match="digest 불일치"):
        cli.cmd_image_pull(args)

    assert not out_file.exists()
    assert not part_file.exists()


def test_cmd_image_pull_interrupt_cleanup_ownership(tmp_path, monkeypatch):
    out_file = tmp_path / "interrupted.qcow2"
    part_file = tmp_path / "interrupted.qcow2.part"

    responses = [
        {"id": "job-intr"},
        {
            "status": "complete",
            "progress_pct": 100,
            "blob_digest": "sha256:" + "a" * 64,
            "download_path": "/blob",
        },
    ]

    def _interrupt_request(method, path):
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "_json_request", lambda method, path, body=None: responses.pop(0))
    monkeypatch.setattr(cli, "_request", _interrupt_request)
    monkeypatch.setattr("time.sleep", lambda secs: None)

    args = cli.build_parser().parse_args(["image", "pull", "img-intr", "--format", "qcow2", "-o", str(out_file)])
    with pytest.raises(cli.PalimpsestCliError, match="작업이 중단되었습니다"):
        cli.cmd_image_pull(args)

    assert not part_file.exists()
