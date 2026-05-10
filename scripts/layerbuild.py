#!/usr/bin/env python3
"""layerbuild — Builder VM용 Union Mount 레이어 빌드 CLI.

Builder VM에서 실행하여 content-addressable 레이어를 생성한다.
환경변수: AFTERGLOW_API_URL, AFTERGLOW_API_TOKEN, LAYER_STORE_RW (마운트 경로)

Usage:
  layerbuild [--dry-run] init <name> --version <ver> [--parent <sha256:hash>] [--ubuntu-base <img>]
  layerbuild [--dry-run] exec <recipe.sh>
  layerbuild [--dry-run] seal
  layerbuild abort
  layerbuild resume-api <sha256:hash>

옵션:
  --dry-run   destructive subprocess(mount/umount/nspawn/chmod/chattr/tar)와 API 호출을
              실제로 실행하지 않고 명령 트레이스만 출력한다. 단일 명령 단위로만
              유효하며 chainable 아님 (state/mkdir 부수효과 미생성).
"""

import argparse
import hashlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("layerbuild")

# ---------------------------------------------------------------------------
# 환경변수 / 경로
# ---------------------------------------------------------------------------

API_URL = os.environ.get("AFTERGLOW_API_URL", "").rstrip("/")
API_TOKEN = os.environ.get("AFTERGLOW_API_TOKEN", "")
LAYER_STORE_RW = Path(os.environ.get("LAYER_STORE_RW", "/mnt/layer-store-rw"))

# 현재 빌드 상태 파일 (단일 Builder VM 가정)
_STATE_FILE = LAYER_STORE_RW / ".layerbuild_state.json"
_WORK_DIR = LAYER_STORE_RW / "build-work"

_PLACEHOLDER_HASH = "sha256:" + ("0" * 64)


# ---------------------------------------------------------------------------
# subprocess / API 헬퍼 (dry-run 일원화)
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str],
    *,
    dry_run: bool = False,
    capture: bool = False,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """subprocess 호출 일원화. dry_run=True면 명령 트레이스만 출력하고 success 반환."""
    log.info("$ %s", " ".join(shlex.quote(c) for c in cmd))
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
    return subprocess.run(cmd, capture_output=capture, check=check)


def _api_get(path: str, *, dry_run: bool = False) -> dict:
    url = f"{API_URL}{path}"
    if dry_run:
        log.info("$ GET %s (dry-run, stub)", url)
        return {"layers": []}
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_post(path: str, data: dict, *, dry_run: bool = False) -> dict:
    url = f"{API_URL}{path}"
    if dry_run:
        log.info("$ POST %s (dry-run, stub)", url)
        return {}
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _require_api_env() -> None:
    """parent 지정 또는 seal 시 필요한 API 환경변수 사전 검증."""
    missing = []
    if not API_URL:
        missing.append("AFTERGLOW_API_URL")
    if not API_TOKEN:
        missing.append("AFTERGLOW_API_TOKEN")
    if missing:
        log.error("필수 환경변수 미설정: %s", ", ".join(missing))
        log.error("Builder VM 환경에서 두 환경변수를 설정한 뒤 다시 실행하세요.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 상태 관리
# ---------------------------------------------------------------------------


def _load_state() -> dict:
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def _clear_state() -> None:
    _STATE_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 결정적 sha256 계산 (tar --sort=name, fixed mtime/uid/gid)
# ---------------------------------------------------------------------------


def _compute_layer_hash(diff_dir: Path, *, dry_run: bool = False) -> str:
    """diff/ 디렉토리를 결정적 tar로 변환 후 sha256 계산.

    dry-run에서는 실제 tar 실행 없이 placeholder hash를 반환 (옵션 B).
    """
    if dry_run:
        log.info("$ tar --sort=name ... -C %s . | sha256sum  (dry-run, placeholder)", diff_dir)
        return _PLACEHOLDER_HASH

    h = hashlib.sha256()
    with tempfile.NamedTemporaryFile(suffix=".tar") as tmp:
        # GNU tar의 결정적 옵션 사용
        result = subprocess.run(
            [
                "tar",
                "--sort=name",
                "--mtime=1970-01-01T00:00:00Z",
                "--owner=0",
                "--group=0",
                "--numeric-owner",
                "-cf",
                tmp.name,
                "-C",
                str(diff_dir),
                ".",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"tar 실패: {result.stderr.decode()}")
        tmp.seek(0)
        while chunk := tmp.read(65536):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------------------
# 서브커맨드: init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """빌드 작업 디렉토리 초기화 + 선택적 overlay 마운트."""
    dry_run: bool = args.dry_run

    state = _load_state()
    if state:
        log.error(
            "진행 중인 빌드가 있습니다. 먼저 'layerbuild seal' 또는 'layerbuild abort'를 실행하세요."
        )
        sys.exit(1)

    # parent 지정 시 API 환경변수 사전 검증
    if args.parent and not dry_run:
        _require_api_env()

    build_id = f"{args.name}-{args.version}-{int(time.time())}"
    work = _WORK_DIR / build_id
    upper = work / "upper"
    work_dir = work / "work"
    merged = work / "merged"

    if not dry_run:
        upper.mkdir(parents=True)
        work_dir.mkdir()
        merged.mkdir()
    else:
        log.info("$ mkdir -p %s %s %s  (dry-run)", upper, work_dir, merged)

    lowerdir_parts: list[str] = []

    if args.parent:
        log.info("부모 레이어 조상 체인 조회: %s", args.parent)
        try:
            chain = _api_get(f"/api/union/layers/{args.parent}/ancestors", dry_run=dry_run)
            layers = chain.get("layers", [])
        except Exception as e:
            log.error("API 호출 실패: %s", e)
            if not dry_run:
                shutil.rmtree(work)
            sys.exit(1)

        for layer in layers:
            layer_id = layer["id"]
            hash_hex = layer_id.removeprefix("sha256:")
            diff = LAYER_STORE_RW / f"sha256-{hash_hex}" / "diff"
            if not dry_run and not diff.is_dir():
                log.error("레이어 diff 디렉토리 없음: %s", diff)
                shutil.rmtree(work)
                sys.exit(1)
            lowerdir_parts.append(str(diff))

        # overlayfs 마운트 (최신 레이어가 leftmost)
        lowerdir = ":".join(reversed(lowerdir_parts)) if lowerdir_parts else str(upper)
        mount_opts = f"lowerdir={lowerdir},upperdir={upper},workdir={work_dir}"
        result = _run(
            ["mount", "-t", "overlay", "overlay", "-o", mount_opts, str(merged)],
            dry_run=dry_run,
            capture=True,
        )
        if result.returncode != 0:
            log.error("overlay 마운트 실패: %s", result.stderr.decode())
            if not dry_run:
                shutil.rmtree(work)
            sys.exit(1)
        log.info("overlay 마운트 완료: %s", merged)
    else:
        # 부모 없음 — merged = upper와 동일하게 바인드 마운트
        result = _run(
            ["mount", "--bind", str(upper), str(merged)],
            dry_run=dry_run,
            capture=True,
        )
        if result.returncode != 0:
            log.error("bind 마운트 실패: %s", result.stderr.decode())
            if not dry_run:
                shutil.rmtree(work)
            sys.exit(1)
        log.info("bind 마운트 완료: %s -> %s", upper, merged)

    state = {
        "build_id": build_id,
        "name": args.name,
        "version": args.version,
        "parent_id": args.parent,
        "ubuntu_base": args.ubuntu_base,
        "work": str(work),
        "upper": str(upper),
        "merged": str(merged),
        "has_overlay": bool(lowerdir_parts),
    }
    if dry_run:
        log.info("(dry-run) state 미작성. 본 명령 후속 명령은 chainable 아님.")
    else:
        _save_state(state)
    log.info("빌드 초기화 완료: %s", build_id)
    log.info("작업 디렉토리: %s", merged)


# ---------------------------------------------------------------------------
# 서브커맨드: exec
# ---------------------------------------------------------------------------


def cmd_exec(args: argparse.Namespace) -> None:
    """systemd-nspawn으로 recipe.sh 실행."""
    dry_run: bool = args.dry_run

    state = _load_state()
    if not state and not dry_run:
        log.error("진행 중인 빌드가 없습니다. 먼저 'layerbuild init'을 실행하세요.")
        sys.exit(1)

    recipe = Path(args.recipe).resolve()
    if not recipe.exists():
        log.error("recipe 파일 없음: %s", recipe)
        sys.exit(1)

    merged = Path(state["merged"]) if state else Path("/dry-run-merged")
    dest_recipe = merged / "tmp" / recipe.name
    if not dry_run:
        dest_recipe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(recipe, dest_recipe)
    else:
        log.info("$ cp %s %s  (dry-run)", recipe, dest_recipe)

    log.info("recipe 실행: %s", recipe.name)
    result = _run(
        [
            "systemd-nspawn",
            "--quiet",
            f"--directory={merged}",
            "--bind=/dev",
            "--bind=/proc",
            "--bind=/sys",
            "/bin/bash",
            f"/tmp/{recipe.name}",
        ],
        dry_run=dry_run,
    )
    if not dry_run:
        dest_recipe.unlink(missing_ok=True)
    if result.returncode != 0:
        log.error("recipe 실행 실패 (exit code %d)", result.returncode)
        sys.exit(result.returncode)
    log.info("recipe 실행 완료")


# ---------------------------------------------------------------------------
# 서브커맨드: seal
# ---------------------------------------------------------------------------


def _build_layer_payload(state: dict, content_hash: str, size_bytes: int, file_count: int) -> dict:
    """API POST에 보낼 레이어 등록 payload."""
    return {
        "name": state["name"],
        "version": state["version"],
        "parent_id": state.get("parent_id"),
        "ubuntu_base": state.get("ubuntu_base"),
        "build_recipe": {},
        "installed_packages": {},
        "content_hash": content_hash,
        "size_bytes": size_bytes,
        "file_count": file_count,
    }


def _write_api_pending(dest_dir: Path, payload: dict) -> None:
    """API 등록 실패 시 .api_pending 마커 작성. resume-api로 재시도 가능."""
    (dest_dir / ".api_pending").write_text(json.dumps(payload, indent=2))


def cmd_seal(args: argparse.Namespace) -> None:
    """레이어 봉인: 해시 계산 -> diff 이동 -> 3-lock -> API POST."""
    dry_run: bool = args.dry_run

    state = _load_state()
    if not state and not dry_run:
        log.error("진행 중인 빌드가 없습니다. 먼저 'layerbuild init'을 실행하세요.")
        sys.exit(1)

    if not state:
        # dry-run + state 없음 — 시연용 stub
        state = {
            "name": "dry-run-name",
            "version": "0.0",
            "parent_id": None,
            "ubuntu_base": None,
            "work": "/dry-run-work",
            "upper": "/dry-run-upper",
            "merged": "/dry-run-merged",
        }

    upper = Path(state["upper"])
    merged = Path(state["merged"])

    log.info("마운트 해제...")
    _run(["umount", str(merged)], dry_run=dry_run, check=not dry_run)

    log.info("콘텐츠 해시 계산 중...")
    content_hash = _compute_layer_hash(upper, dry_run=dry_run)
    hash_hex = content_hash.removeprefix("sha256:")
    log.info("콘텐츠 해시: %s", content_hash)

    dest_dir = LAYER_STORE_RW / f"sha256-{hash_hex}"
    diff_dest = dest_dir / "diff"

    if dry_run:
        log.info("$ mkdir -p %s  (dry-run)", dest_dir)
        log.info("$ mv %s %s  (dry-run)", upper, diff_dest)
        size_bytes = 0
        file_count = 0
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)
        upper.rename(diff_dest)
        file_count = sum(1 for _ in diff_dest.rglob("*") if _.is_file())
        size_bytes = sum(f.stat().st_size for f in diff_dest.rglob("*") if f.is_file())

        layer_json = {
            "id": content_hash,
            "name": state["name"],
            "version": state["version"],
            "parent_id": state.get("parent_id"),
            "ubuntu_base": state.get("ubuntu_base"),
            "content_hash": content_hash,
            "size_bytes": size_bytes,
            "file_count": file_count,
        }
        (dest_dir / "layer.json").write_text(json.dumps(layer_json, indent=2))

    # 3-lock: chmod -> chattr -> DB seal
    log.info("불변 락 적용 중...")
    _run(["chmod", "-R", "a-w", str(diff_dest)], dry_run=dry_run, check=not dry_run)
    # chattr +i는 CephFS에서 지원하지 않을 수 있음 — 실패해도 계속 진행
    result = _run(["chattr", "-R", "+i", str(diff_dest)], dry_run=dry_run, capture=True)
    if not dry_run and result.returncode != 0:
        log.warning("chattr +i 실패 (CephFS는 미지원): %s", result.stderr.decode().strip())

    # API 레이어 등록
    log.info("API 레이어 등록...")
    payload = _build_layer_payload(state, content_hash, size_bytes, file_count)
    if dry_run:
        log.info("$ POST /api/union/layers (dry-run, stub) — payload: %s", payload)
        log.info("$ POST /api/union/layers/%s/seal (dry-run, stub)", content_hash)
    elif not API_URL or not API_TOKEN:
        log.warning("AFTERGLOW_API_URL 또는 AFTERGLOW_API_TOKEN 미설정 — API 등록 생략")
        _write_api_pending(dest_dir, payload)
        log.warning(".api_pending 마커 기록 — `layerbuild resume-api %s`로 재시도 가능", content_hash)
    else:
        try:
            _api_post("/api/union/layers", payload)
            log.info("레이어 등록 완료: %s", content_hash)
            _api_post(f"/api/union/layers/{content_hash}/seal", {})
            log.info("레이어 봉인 완료")
        except Exception as e:
            log.error("API 호출 실패: %s", e)
            _write_api_pending(dest_dir, payload)
            log.error(
                "레이어 디렉토리는 디스크에 생성됐습니다. `layerbuild resume-api %s`로 재시도하세요.",
                content_hash,
            )

    # 작업 디렉토리 정리
    if not dry_run:
        work = Path(state["work"])
        shutil.rmtree(work, ignore_errors=True)
        _clear_state()

    log.info("레이어 봉인 완료: %s", content_hash)
    print(content_hash)


# ---------------------------------------------------------------------------
# 서브커맨드: abort
# ---------------------------------------------------------------------------


def cmd_abort(args: argparse.Namespace) -> None:
    """진행 중인 빌드 취소 및 정리."""
    state = _load_state()
    if not state:
        log.info("진행 중인 빌드가 없습니다.")
        return

    merged = Path(state["merged"])
    _run(["umount", str(merged)], dry_run=False, capture=True)

    work = Path(state["work"])
    shutil.rmtree(work, ignore_errors=True)
    _clear_state()
    log.info("빌드 취소 완료")


# ---------------------------------------------------------------------------
# 서브커맨드: resume-api
# ---------------------------------------------------------------------------


def cmd_resume_api(args: argparse.Namespace) -> None:
    """seal 시 API 등록에 실패한 레이어를 재등록.

    `.api_pending` 마커를 읽고 POST 두 번 (등록 + 봉인) 재시도. 성공 시 마커 삭제.
    """
    content_hash: str = args.layer_id
    if not content_hash.startswith("sha256:"):
        log.error("layer_id는 'sha256:' 접두사를 포함해야 합니다.")
        sys.exit(1)

    hash_hex = content_hash.removeprefix("sha256:")
    dest_dir = LAYER_STORE_RW / f"sha256-{hash_hex}"
    marker = dest_dir / ".api_pending"
    if not marker.is_file():
        log.error(".api_pending 마커 없음: %s", marker)
        log.error("seal 시 API 호출이 실패했거나 이미 등록 완료된 레이어입니다.")
        sys.exit(1)

    _require_api_env()
    payload = json.loads(marker.read_text())

    try:
        _api_post("/api/union/layers", payload)
        log.info("레이어 재등록 완료: %s", content_hash)
        _api_post(f"/api/union/layers/{content_hash}/seal", {})
        log.info("레이어 봉인 완료")
    except Exception as e:
        log.error("API 재등록 실패: %s", e)
        sys.exit(1)

    marker.unlink()
    log.info(".api_pending 마커 삭제 완료")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="layerbuild — Union Mount 레이어 빌드 CLI")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="destructive subprocess + API 호출을 실제 실행하지 않고 트레이스만 출력",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="빌드 작업 디렉토리 초기화")
    p_init.add_argument("name", help="레이어 이름")
    p_init.add_argument("--version", required=True, help="레이어 버전")
    p_init.add_argument("--parent", metavar="SHA256", help="부모 레이어 id (sha256:...)")
    p_init.add_argument("--ubuntu-base", metavar="IMAGE", help="Ubuntu 베이스 이미지 이름")
    p_init.set_defaults(func=cmd_init)

    p_exec = sub.add_parser("exec", help="recipe 스크립트 실행")
    p_exec.add_argument("recipe", help="실행할 bash 스크립트 경로")
    p_exec.set_defaults(func=cmd_exec)

    p_seal = sub.add_parser("seal", help="레이어 봉인 및 API 등록")
    p_seal.set_defaults(func=cmd_seal)

    p_abort = sub.add_parser("abort", help="진행 중인 빌드 취소")
    p_abort.set_defaults(func=cmd_abort)

    p_resume = sub.add_parser("resume-api", help="seal 시 API 실패한 레이어 재등록")
    p_resume.add_argument("layer_id", help="재등록할 레이어 id (sha256:...)")
    p_resume.set_defaults(func=cmd_resume_api)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
