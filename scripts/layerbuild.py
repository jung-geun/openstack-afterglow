#!/usr/bin/env python3
"""layerbuild — Builder VM용 Union Mount 레이어 빌드 CLI.

Builder VM에서 실행하여 content-addressable 레이어를 생성한다.
환경변수: AFTERGLOW_API_URL, AFTERGLOW_API_TOKEN, LAYER_STORE_RW (마운트 경로)

Usage:
  layerbuild init <name> --version <ver> [--parent <sha256:hash>] [--ubuntu-base <img>]
  layerbuild exec <recipe.sh>
  layerbuild seal
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import urllib.request
import urllib.error

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


# ---------------------------------------------------------------------------
# API 헬퍼
# ---------------------------------------------------------------------------

def _api_get(path: str) -> dict:
    url = f"{API_URL}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {API_TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_post(path: str, data: dict) -> dict:
    url = f"{API_URL}{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


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

def _compute_layer_hash(diff_dir: Path) -> str:
    """diff/ 디렉토리를 결정적 tar로 변환 후 sha256 계산."""
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
                "-cf", tmp.name,
                "-C", str(diff_dir),
                ".",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"tar 실패: {result.stderr.decode()}")
        # 청크 단위로 해시 계산
        tmp.seek(0)
        while chunk := tmp.read(65536):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------------------
# 서브커맨드: init
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    """빌드 작업 디렉토리 초기화 + 선택적 overlay 마운트."""
    state = _load_state()
    if state:
        log.error("진행 중인 빌드가 있습니다. 먼저 'layerbuild seal' 또는 'layerbuild abort'를 실행하세요.")
        sys.exit(1)

    build_id = f"{args.name}-{args.version}-{int(time.time())}"
    work = _WORK_DIR / build_id
    upper = work / "upper"
    work_dir = work / "work"
    merged = work / "merged"

    upper.mkdir(parents=True)
    work_dir.mkdir()
    merged.mkdir()

    lowerdir_parts: list[str] = []

    if args.parent:
        # 조상 체인 조회
        log.info("부모 레이어 조상 체인 조회: %s", args.parent)
        try:
            chain = _api_get(f"/api/union/layers/{args.parent}/ancestors")
            layers = chain.get("layers", [])
        except Exception as e:
            log.error("API 호출 실패: %s", e)
            shutil.rmtree(work)
            sys.exit(1)

        for layer in layers:
            layer_id = layer["id"]
            hash_hex = layer_id.removeprefix("sha256:")
            diff = LAYER_STORE_RW / f"sha256-{hash_hex}" / "diff"
            if not diff.is_dir():
                log.error("레이어 diff 디렉토리 없음: %s", diff)
                shutil.rmtree(work)
                sys.exit(1)
            lowerdir_parts.append(str(diff))

        # overlayfs 마운트 (최신 레이어가 leftmost)
        lowerdir = ":".join(reversed(lowerdir_parts))
        mount_opts = f"lowerdir={lowerdir},upperdir={upper},workdir={work_dir}"
        result = subprocess.run(
            ["mount", "-t", "overlay", "overlay", "-o", mount_opts, str(merged)],
            capture_output=True,
        )
        if result.returncode != 0:
            log.error("overlay 마운트 실패: %s", result.stderr.decode())
            shutil.rmtree(work)
            sys.exit(1)
        log.info("overlay 마운트 완료: %s", merged)
    else:
        # 부모 없음 — merged = upper와 동일하게 바인드 마운트
        result = subprocess.run(
            ["mount", "--bind", str(upper), str(merged)],
            capture_output=True,
        )
        if result.returncode != 0:
            log.error("bind 마운트 실패: %s", result.stderr.decode())
            shutil.rmtree(work)
            sys.exit(1)
        log.info("bind 마운트 완료: %s → %s", upper, merged)

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
    _save_state(state)
    log.info("빌드 초기화 완료: %s", build_id)
    log.info("작업 디렉토리: %s", merged)


# ---------------------------------------------------------------------------
# 서브커맨드: exec
# ---------------------------------------------------------------------------

def cmd_exec(args: argparse.Namespace) -> None:
    """systemd-nspawn으로 recipe.sh 실행."""
    state = _load_state()
    if not state:
        log.error("진행 중인 빌드가 없습니다. 먼저 'layerbuild init'을 실행하세요.")
        sys.exit(1)

    recipe = Path(args.recipe).resolve()
    if not recipe.exists():
        log.error("recipe 파일 없음: %s", recipe)
        sys.exit(1)

    merged = Path(state["merged"])
    # recipe를 merged 안으로 복사
    dest_recipe = merged / "tmp" / recipe.name
    dest_recipe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(recipe, dest_recipe)

    log.info("recipe 실행: %s", recipe.name)
    result = subprocess.run(
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
    )
    dest_recipe.unlink(missing_ok=True)
    if result.returncode != 0:
        log.error("recipe 실행 실패 (exit code %d)", result.returncode)
        sys.exit(result.returncode)
    log.info("recipe 실행 완료")


# ---------------------------------------------------------------------------
# 서브커맨드: seal
# ---------------------------------------------------------------------------

def cmd_seal(args: argparse.Namespace) -> None:
    """레이어 봉인: 해시 계산 → diff 이동 → 3-lock → API POST."""
    state = _load_state()
    if not state:
        log.error("진행 중인 빌드가 없습니다. 먼저 'layerbuild init'을 실행하세요.")
        sys.exit(1)

    upper = Path(state["upper"])
    merged = Path(state["merged"])

    # overlay/bind 마운트 해제
    log.info("마운트 해제...")
    subprocess.run(["umount", str(merged)], check=True)

    # 결정적 sha256 계산
    log.info("콘텐츠 해시 계산 중...")
    content_hash = _compute_layer_hash(upper)
    hash_hex = content_hash.removeprefix("sha256:")
    log.info("콘텐츠 해시: %s", content_hash)

    # diff 디렉토리로 이동
    dest_dir = LAYER_STORE_RW / f"sha256-{hash_hex}"
    diff_dest = dest_dir / "diff"
    dest_dir.mkdir(parents=True, exist_ok=True)
    upper.rename(diff_dest)

    # 파일 수, 크기 계산
    file_count = sum(1 for _ in diff_dest.rglob("*") if _.is_file())
    size_bytes = sum(f.stat().st_size for f in diff_dest.rglob("*") if f.is_file())

    # layer.json 기록
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

    # 3-lock: chmod → chattr → DB seal
    log.info("불변 락 적용 중...")
    subprocess.run(["chmod", "-R", "a-w", str(diff_dest)], check=True)
    # chattr +i는 CephFS에서 지원하지 않을 수 있음 — 실패해도 계속 진행
    result = subprocess.run(["chattr", "-R", "+i", str(diff_dest)], capture_output=True)
    if result.returncode != 0:
        log.warning("chattr +i 실패 (CephFS는 미지원): %s", result.stderr.decode().strip())

    # API 레이어 등록
    log.info("API 레이어 등록...")
    if not API_URL or not API_TOKEN:
        log.warning("AFTERGLOW_API_URL 또는 AFTERGLOW_API_TOKEN 미설정 — API 등록 생략")
    else:
        try:
            _api_post("/api/union/layers", {
                "name": state["name"],
                "version": state["version"],
                "parent_id": state.get("parent_id"),
                "ubuntu_base": state.get("ubuntu_base"),
                "build_recipe": {},
                "installed_packages": {},
                "content_hash": content_hash,
                "size_bytes": size_bytes,
                "file_count": file_count,
            })
            log.info("레이어 등록 완료: %s", content_hash)
            _api_post(f"/api/union/layers/{content_hash}/seal", {})
            log.info("레이어 봉인 완료")
        except Exception as e:
            log.error("API 호출 실패: %s", e)
            log.error("수동으로 레이어를 등록/봉인해야 합니다.")

    # 작업 디렉토리 정리
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
    subprocess.run(["umount", str(merged)], capture_output=True)

    work = Path(state["work"])
    shutil.rmtree(work, ignore_errors=True)
    _clear_state()
    log.info("빌드 취소 완료")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="layerbuild — Union Mount 레이어 빌드 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    p_init = sub.add_parser("init", help="빌드 작업 디렉토리 초기화")
    p_init.add_argument("name", help="레이어 이름")
    p_init.add_argument("--version", required=True, help="레이어 버전")
    p_init.add_argument("--parent", metavar="SHA256", help="부모 레이어 id (sha256:...)")
    p_init.add_argument("--ubuntu-base", metavar="IMAGE", help="Ubuntu 베이스 이미지 이름")
    p_init.set_defaults(func=cmd_init)

    # exec
    p_exec = sub.add_parser("exec", help="recipe 스크립트 실행")
    p_exec.add_argument("recipe", help="실행할 bash 스크립트 경로")
    p_exec.set_defaults(func=cmd_exec)

    # seal
    p_seal = sub.add_parser("seal", help="레이어 봉인 및 API 등록")
    p_seal.set_defaults(func=cmd_seal)

    # abort
    p_abort = sub.add_parser("abort", help="진행 중인 빌드 취소")
    p_abort.set_defaults(func=cmd_abort)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
