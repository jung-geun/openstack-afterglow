#!/usr/bin/env python3
"""palimpsest — 로컬에서 레이어를 빌드해 허브에 올리는 CLI.

사용자 머신에서 도는 도구다. 백엔드는 사용자 머신에 접근할 수 없으므로, 베이스 이미지를
받고 빌드하고 올리는 일은 여기서 한다. **표준 라이브러리만 쓴다** — 사용자가 별도 의존성을
설치하지 않아도 되게.

전형적인 흐름:

    export PALIMPSEST_URL=https://cloud.example.com
    export PALIMPSEST_TOKEN=<access token>

    palimpsest images                                  # 베이스 cloud image 목록
    palimpsest pull sha256:<image-digest> -o base.qcow2

    # ... KVM 으로 base.qcow2 를 띄워 원하는 걸 설치한 뒤,
    #     변경분 디렉터리를 뽑아 squashfs 로 만든다 ...
    palimpsest pack ./rootfs-delta -o mylayer.sqsh

    palimpsest push mylayer.sqsh --name mylayer --parent sha256:<parent> \
        --base-image sha256:<image-digest>

`pack` 은 `mksquashfs` 를 부른다(squashfs-tools 필요). 나머지는 순수 HTTP 다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_CHUNK = 1024 * 1024
_UPLOAD_CHUNK = 8 * 1024 * 1024


class PalimpsestCliError(RuntimeError):
    """사용자에게 그대로 보여줄 오류."""


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _base_url() -> str:
    url = (os.environ.get("PALIMPSEST_URL") or "").strip().rstrip("/")
    if not url:
        raise PalimpsestCliError("PALIMPSEST_URL 환경변수를 설정하세요 (예: https://cloud.example.com)")
    return url


def _token() -> str:
    token = (os.environ.get("PALIMPSEST_TOKEN") or "").strip()
    if not token:
        raise PalimpsestCliError("PALIMPSEST_TOKEN 환경변수를 설정하세요")
    return token


def _request(method: str, path: str, *, body: bytes | None = None, content_type: str | None = None):
    url = f"{_base_url()}/api/v1/palimpsest/hub{path}"
    headers = {"Authorization": f"Bearer {_token()}"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=300)  # noqa: S310 — URL 은 사용자 환경변수
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode(errors="replace")
        raise PalimpsestCliError(f"{method} {path} 실패 (HTTP {exc.code}): {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise PalimpsestCliError(f"{_base_url()} 에 연결할 수 없습니다: {exc.reason}") from exc


def _json_request(method: str, path: str, payload: dict | None = None) -> dict | list:
    body = json.dumps(payload).encode() if payload is not None else None
    with _request(method, path, body=body, content_type="application/json" if body else None) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# 순수 헬퍼 (테스트 대상)
# ---------------------------------------------------------------------------


def digest_file(path: Path) -> tuple[str, int]:
    """파일의 sha256 과 크기. 업로드 전에 미리 계산해 서버가 재검증할 수 있게 한다."""
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            sha.update(chunk)
            size += len(chunk)
    return f"sha256:{sha.hexdigest()}", size


def build_mksquashfs_command(source: Path, output: Path) -> list[str]:
    """`pack` 이 실행할 명령. 백엔드 빌드 경로(`recipe_blocks.py`)와 같은 옵션을 쓴다 —
    허브에 올라간 레이어가 어디서 만들어졌든 같은 성질을 갖게 하기 위해서다.

    셸을 거치지 않도록 인자 리스트로 만든다.
    """
    if not source.is_dir():
        raise PalimpsestCliError(f"소스 디렉터리가 아닙니다: {source}")
    return [
        "mksquashfs",
        str(source),
        str(output),
        "-comp",
        "zstd",
        "-Xcompression-level",
        "3",
        "-noappend",
        "-no-exports",
    ]


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TiB"


# ---------------------------------------------------------------------------
# 명령
# ---------------------------------------------------------------------------


def cmd_images(args) -> int:
    query = {}
    for key in ("ubuntu_base", "arch", "os_variant", "disk_format"):
        value = getattr(args, key, None)
        if value:
            query[key] = value
    path = "/images" + (f"?{urllib.parse.urlencode(query)}" if query else "")
    rows = _json_request("GET", path)
    if not rows:
        print("베이스 이미지가 없습니다.")
        return 0
    for row in rows:
        print(
            f"{row['blob_digest']}  {row['name']:<24} "
            f"{row.get('ubuntu_base') or '-':<14} {row.get('arch') or '-':<9} "
            f"{row.get('disk_format') or '-':<6} {format_size(row['size_bytes'])}"
        )
    return 0


def cmd_layers(args) -> int:
    query = {k: v for k, v in (("name", args.name), ("kind", args.kind)) if v}
    path = "/layers" + (f"?{urllib.parse.urlencode(query)}" if query else "")
    rows = _json_request("GET", path)
    for row in rows:
        parent = row.get("parent_digest") or "-"
        print(f"{row['blob_digest']}  {row['name']:<24} {row['kind']:<12} parent={parent}")
    return 0


def cmd_pull(args) -> int:
    """blob 을 내려받는다. 받은 뒤 digest 를 **재계산해 검증**한다."""
    output = Path(args.output)
    with _request("GET", f"/layers/{args.digest}/blob") as resp, output.open("wb") as out:
        shutil.copyfileobj(resp, out, _CHUNK)
    actual, size = digest_file(output)
    if actual != args.digest:
        output.unlink(missing_ok=True)
        raise PalimpsestCliError(f"digest 불일치 — 요청={args.digest} 실제={actual}. 파일을 삭제했습니다")
    print(f"{output} ({format_size(size)}) — digest 검증 완료")
    return 0


def cmd_pack(args) -> int:
    output = Path(args.output)
    command = build_mksquashfs_command(Path(args.source), output)
    try:
        subprocess.run(command, check=True)  # noqa: S603 — 인자 리스트, 셸 미사용
    except FileNotFoundError as exc:
        raise PalimpsestCliError("mksquashfs 를 찾을 수 없습니다 (squashfs-tools 패키지 필요)") from exc
    except subprocess.CalledProcessError as exc:
        raise PalimpsestCliError(f"mksquashfs 실패 (exit={exc.returncode})") from exc
    digest, size = digest_file(output)
    print(f"{output} ({format_size(size)})\n{digest}")
    return 0


def cmd_push(args) -> int:
    """레이어(또는 cloud image)를 허브에 올린다.

    digest 를 먼저 선언하므로 이미 있는 콘텐츠는 업로드 자체가 생략된다.
    """
    path = Path(args.file)
    if not path.is_file():
        raise PalimpsestCliError(f"파일이 없습니다: {path}")
    digest, size = digest_file(path)
    print(f"{path.name}: {digest} ({format_size(size)})")

    started = _json_request("POST", "/uploads", {"digest": digest})
    if started.get("completed"):
        print("이미 허브에 있는 콘텐츠입니다 — 업로드를 생략합니다.")
        session_id = None
    else:
        session_id = started["session_id"]
        sent = 0
        with path.open("rb") as handle:
            while chunk := handle.read(_UPLOAD_CHUNK):
                with _request(
                    "PATCH", f"/uploads/{session_id}", body=chunk, content_type="application/octet-stream"
                ):
                    pass
                sent += len(chunk)
                print(f"\r  업로드 {format_size(sent)} / {format_size(size)}", end="", file=sys.stderr)
        print("", file=sys.stderr)

    meta: dict = {"name": args.name, "kind": args.kind, "is_published": bool(args.publish)}
    if args.parent:
        meta["parent_digest"] = args.parent
    if args.base_image:
        meta["base_image_digest"] = args.base_image
    if args.ubuntu_base:
        meta["ubuntu_base"] = args.ubuntu_base
    if args.kind == "cloud-image":
        meta["disk_format"] = args.disk_format
        meta["arch"] = args.arch
        if args.os_variant:
            meta["os_variant"] = args.os_variant

    if session_id is None:
        print(f"등록 완료: {digest}")
        return 0

    result = _json_request("PUT", f"/uploads/{session_id}", meta)
    print(f"등록 완료: {result['blob_digest']}")
    return 0


def cmd_bundle(args) -> int:
    payload = {"refs": args.refs, "include_base_image": bool(args.include_base_image)}
    output = Path(args.output)
    body = json.dumps(payload).encode()
    with _request("POST", "/bundles", body=body, content_type="application/json") as resp:
        with output.open("wb") as out:
            shutil.copyfileobj(resp, out, _CHUNK)
    print(f"{output} ({format_size(output.stat().st_size)})")
    return 0


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palimpsest", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    images = sub.add_parser("images", help="베이스 cloud image 목록")
    images.add_argument("--ubuntu-base", dest="ubuntu_base")
    images.add_argument("--arch")
    images.add_argument("--os-variant", dest="os_variant")
    images.add_argument("--disk-format", dest="disk_format", choices=["qcow2", "raw"])
    images.set_defaults(func=cmd_images)

    layers = sub.add_parser("layers", help="레이어 목록")
    layers.add_argument("--name")
    layers.add_argument("--kind")
    layers.set_defaults(func=cmd_layers)

    pull = sub.add_parser("pull", help="blob 다운로드 (digest 재검증 포함)")
    pull.add_argument("digest")
    pull.add_argument("-o", "--output", required=True)
    pull.set_defaults(func=cmd_pull)

    pack = sub.add_parser("pack", help="디렉터리를 squashfs 레이어로 만든다")
    pack.add_argument("source")
    pack.add_argument("-o", "--output", required=True)
    pack.set_defaults(func=cmd_pack)

    push = sub.add_parser("push", help="레이어/이미지를 허브에 올린다")
    push.add_argument("file")
    push.add_argument("--name", required=True)
    push.add_argument("--kind", default="squashfs")
    push.add_argument("--parent", help="부모 레이어 digest")
    push.add_argument("--base-image", dest="base_image", help="이 레이어가 올라간 베이스 이미지 digest")
    push.add_argument("--ubuntu-base", dest="ubuntu_base")
    push.add_argument("--disk-format", dest="disk_format", default="qcow2", choices=["qcow2", "raw"])
    push.add_argument("--arch", default="x86_64", choices=["x86_64", "aarch64"])
    push.add_argument("--os-variant", dest="os_variant")
    push.add_argument("--publish", action="store_true", help="사이트에 공개")
    push.set_defaults(func=cmd_push)

    bundle = sub.add_parser("bundle", help="부모 체인을 OCI 번들로 내려받는다")
    bundle.add_argument("refs", nargs="+")
    bundle.add_argument("-o", "--output", required=True)
    bundle.add_argument(
        "--include-base-image", dest="include_base_image", action="store_true", help="베이스 이미지까지 포함"
    )
    bundle.set_defaults(func=cmd_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PalimpsestCliError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
