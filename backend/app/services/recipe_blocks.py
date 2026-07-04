"""라이브러리 빌드 레시피 블록 — 조합 가능한 셸 스크립트 조각 생성기.

빌더 VM cloud-init(run-build.sh)에서 실행되는 스크립트 조각을 만든다.
새 라이브러리 레시피는 이 블록들을 조합해 정의한다 (library_recipes.py 참조).

블록 계약(작성 규칙):
  - 산출물은 레이어 루트인 /mnt/share 아래 FHS 레이아웃(usr/local/..., etc/...)으로 배치한다.
    consumer VM은 이 share를 overlayfs lowerdir로 머지해 /opt/layers/merged 로 노출한다.
  - run-build.sh 는 `set -euo pipefail` 로 실행된다 — 블록 내 명령 실패 시 빌드 전체가 실패한다.
  - 패키지명 등 외부 입력은 화이트리스트 정규식 검증 + shlex.quote 이중 방어한다.
  - 블록은 멱등 가드를 갖춰 같은 레시피에서 여러 번 포함되어도 안전해야 한다.
"""

from __future__ import annotations

import base64
import re
import shlex
from urllib.parse import urlsplit

LAYER_ROOT = "/mnt/share"

# ---------------------------------------------------------------------------
# 입력 검증 (화이트리스트)
# ---------------------------------------------------------------------------

# Debian 패키지명 정책: 소문자 영숫자 시작, [a-z0-9.+-]
_APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")
# squashfs/프로필 이름: 소문자 영숫자 시작, [a-z0-9.+-]  (apt 이름과 동일 정책)
_LAYER_NAME_RE = _APT_NAME_RE
# pip 패키지 스펙: 이름[extras]제약 — 공백·셸 메타문자 불허
_PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\[\],<>=!~+*-]*$")
# Python 버전: major.minor
_PY_VERSION_RE = re.compile(r"^\d+\.\d+$")
_NVIDIA_DRIVER_BRANCH_VALUES = {"550", "570", "575", "580"}
# debconf 셀렉션 라인: "패키지 키 타입 값"
_DEBCONF_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]* [A-Za-z0-9/._-]+ [a-z]+ [^\n\r]*$")
# Manila NFS export 경로: host:/path 형태, 셸 메타문자·개행 불허
_NFS_EXPORT_RE = re.compile(r"^[0-9a-zA-Z.\[\]:/_\-]+$")
# squashfs 파일명: <name>[-<ts>].sqsh
_SQSH_FILENAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]*\.sqsh$")
_PIP_SOURCE_URL_FIELDS = "pip_index_url, pip_extra_index_urls, pip_find_links"


def _validate_pip_source_url(value: str) -> str:
    url = str(value).strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"pip source URL은 http(s) URL이어야 합니다: {value!r}")
    if parsed.username or parsed.password:
        raise ValueError("pip source URL에는 사용자명/비밀번호를 포함할 수 없습니다")
    if parsed.query or parsed.fragment:
        raise ValueError("pip source URL에는 query 또는 fragment를 포함할 수 없습니다")
    if any(ch in url for ch in "\r\n\t '\"`$\\;|<>"):
        raise ValueError(f"pip source URL에 허용되지 않는 문자가 있습니다: {value!r}")
    return url


def _pip_source_args(
    pip_index_url: str | None,
    pip_extra_index_urls: list[str] | None,
    pip_find_links: list[str] | None,
) -> str:
    args: list[str] = []
    if pip_index_url:
        args.extend(["--index-url", _validate_pip_source_url(pip_index_url)])
    for url in pip_extra_index_urls or []:
        args.extend(["--extra-index-url", _validate_pip_source_url(url)])
    for url in pip_find_links or []:
        args.extend(["--find-links", _validate_pip_source_url(url)])
    return " ".join(shlex.quote(arg) for arg in args)


def _validate(items: list[str], pattern: re.Pattern, kind: str) -> None:
    for item in items:
        if not pattern.match(item):
            raise ValueError(f"유효하지 않은 {kind}: {item!r}")


# ---------------------------------------------------------------------------
# 공용: 병렬 복사기 (NFS RTT 지연 완화 — cp -a 대비 ~16배)
# ---------------------------------------------------------------------------

_PYCOPY_PATH = "/tmp/aft_pycopy.py"

# - 심볼릭 링크/권한/시간 보존, 소유자 보존(chown best-effort, no_root_squash 전제)
# - OverlayFS whiteout(char device) 등 특수 파일은 건너뜀
_PYCOPY_SOURCE = """\
import os, sys, shutil, stat, concurrent.futures
src, dst = sys.argv[1], sys.argv[2]
items = []
for dp, dirs, files in os.walk(src, followlinks=False):
    rel = os.path.relpath(dp, src)
    td = dst if rel == "." else os.path.join(dst, rel)
    os.makedirs(td, exist_ok=True)
    try:
        st = os.stat(dp)
        os.chmod(td, stat.S_IMODE(st.st_mode))
        os.chown(td, st.st_uid, st.st_gid)
    except OSError:
        pass
    for n in files:
        items.append((os.path.join(dp, n), os.path.join(td, n)))
    real = []
    for n in dirs:
        s = os.path.join(dp, n)
        if os.path.islink(s):
            items.append((s, os.path.join(td, n)))
        else:
            real.append(n)
    dirs[:] = real
def cp(pair):
    s, d = pair
    if os.path.islink(s):
        try:
            os.symlink(os.readlink(s), d)
        except FileExistsError:
            pass
        return
    st = os.lstat(s)
    if not stat.S_ISREG(st.st_mode):
        return
    shutil.copy2(s, d)
    try:
        os.chown(d, st.st_uid, st.st_gid)
    except OSError:
        pass
with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
    list(ex.map(cp, items))
"""


def _ensure_pycopy() -> str:
    """병렬 복사기 스크립트를 빌더 VM에 1회 배치하는 조각 (멱등)."""
    return f"if [ ! -f {_PYCOPY_PATH} ]; then\ncat > {_PYCOPY_PATH} << 'AFT_PYEOF'\n{_PYCOPY_SOURCE}AFT_PYEOF\nfi\n"


def parallel_copy(src_shell: str, dst_shell: str) -> str:
    """src → dst 병렬 복사 조각.

    Args:
        src_shell / dst_shell: 이미 셸-안전한 토큰. 리터럴 경로는 shlex.quote 후
            전달하고, 셸 변수는 '"$VAR"' 형태로 전달한다.
    """
    return _ensure_pycopy() + f"python3 {_PYCOPY_PATH} {src_shell} {dst_shell}\n"


# ---------------------------------------------------------------------------
# uv 기반 블록 (Python 생태계)
# ---------------------------------------------------------------------------

_UV_PYTHON_DIR = "/opt/aft-uvpy"


def uv_bootstrap() -> str:
    """uv 설치 (정적 바이너리). 모든 uv 기반 블록의 선행 단계."""
    return (
        "export PATH=/usr/local/bin:$PATH\n"
        "if ! command -v uv >/dev/null 2>&1; then\n"
        "curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh\n"
        "fi\n"
    )


def _resolve_uv_python(python_version: str) -> str:
    """uv 관리 CPython 설치 + $PYDIR/$PYBIN 설정 조각 (멱등).

    uv는 cpython-X.Y-* (심볼릭 링크) → cpython-X.Y.Z-* (실제 디렉토리) 구조로 설치한다.
    """
    _validate([python_version], _PY_VERSION_RE, "Python 버전")
    v = python_version  # 검증 완료 — [0-9.]만 포함
    return (
        f"uv python install cpython-{v} --install-dir {_UV_PYTHON_DIR}\n"
        "PYDIR=\n"
        f"for _d in {_UV_PYTHON_DIR}/cpython-{v}*; do\n"
        '  PYDIR=$(readlink -f "$_d"); break\n'
        "done\n"
        f'if [ -z "$PYDIR" ] || [ ! -d "$PYDIR" ]; then echo "uv python {v} 미발견" >&2; exit 1; fi\n'
        f'PYBIN="$PYDIR/bin/python{v}"\n'
        f'if [ ! -x "$PYBIN" ]; then echo "python{v} 실행 파일 미발견: $PYBIN" >&2; exit 1; fi\n'
    )


def python_layer(python_version: str) -> str:
    """uv standalone CPython을 레이어(/mnt/share/usr/local)에 배치하는 블록.

    uv CPython은 재배치 가능(relocatable)하므로 consumer가 overlayfs merged 경로에서
    그대로 실행할 수 있다.
    """
    _validate([python_version], _PY_VERSION_RE, "Python 버전")
    v = python_version
    return (
        _resolve_uv_python(v)
        + f"mkdir -p {LAYER_ROOT}/usr/local\n"
        + parallel_copy('"$PYDIR"', f"{LAYER_ROOT}/usr/local")
        + f"mkdir -p {LAYER_ROOT}/usr/local/lib/python{v}/site-packages\n"
    )


def pip_layer(packages: list[str], python_version: str = "3.11") -> str:
    """pip 패키지들을 레이어 site-packages에 설치하는 블록.

    apt python에 의존하지 않고 uv 관리 CPython으로 설치한다 (Ubuntu 버전 무관).
    consumer는 python<ver> 레이어와 함께 마운트하고 PYTHONPATH로 노출한다.
    """
    if not packages:
        raise ValueError("packages가 비어 있습니다")
    _validate(packages, _PIP_SPEC_RE, "pip 패키지 스펙")
    _validate([python_version], _PY_VERSION_RE, "Python 버전")
    v = python_version
    pkgs = " ".join(shlex.quote(p) for p in packages)
    site = f"{LAYER_ROOT}/usr/local/lib/python{v}/site-packages"
    return (
        _resolve_uv_python(v)
        + f"mkdir -p {site}\n"
        + f'uv pip install --python "$PYBIN" --no-cache --target {site} {pkgs}\n'
    )


# ---------------------------------------------------------------------------
# apt 캡처 블록 (임의 시스템 패키지 스택 — apache/php 등)
# ---------------------------------------------------------------------------


def apt_capture_layer(
    packages: list[str],
    *,
    debconf_selections: list[str] | None = None,
    capture_size_gb: int = 8,
) -> str:
    """apt 패키지 설치 변경분을 OverlayFS로 캡처해 레이어에 배치하는 블록.

    동작:
      1. 루프백 ext4 이미지(sparse)를 만들어 upper/work 용 로컬 FS 확보
         (NFS는 overlayfs upperdir로 사용 불가, lowerdir=/ 하위 경로는 overlap 제한)
      2. lowerdir=/ 인 overlay를 구성하고 chroot에서 apt-get install 실행
         → 모든 파일 변경(postinst 산출물 포함)이 upper에 격리 캡처됨
      3. 휘발성 경로(tmp, var/cache, var/log 등) 제거 후 upper → /mnt/share 병렬 복사

    어떤 apt 패키지 조합이든 FHS 레이아웃 그대로 레이어화된다.
    """
    if not packages:
        raise ValueError("packages가 비어 있습니다")
    _validate(packages, _APT_NAME_RE, "apt 패키지명")
    if debconf_selections:
        _validate(debconf_selections, _DEBCONF_RE, "debconf 셀렉션")
    if not (1 <= capture_size_gb <= 64):
        raise ValueError(f"capture_size_gb 범위 초과: {capture_size_gb}")

    pkgs = " ".join(shlex.quote(p) for p in packages)

    # force-unsafe-io: dpkg fsync 생략 (이미지 빌드 표준 기법) — ephemeral VM이라 안전.
    # 설치 중에만 적용하고 레이어에 포함되지 않도록 종료 전 제거한다.
    chroot_lines = [
        "export DEBIAN_FRONTEND=noninteractive",
        "mkdir -p /etc/dpkg/dpkg.cfg.d",
        "echo force-unsafe-io > /etc/dpkg/dpkg.cfg.d/aft-unsafe-io",
    ]
    if debconf_selections:
        lines = " ".join(shlex.quote(line) for line in debconf_selections)
        chroot_lines.append(f"printf '%s\\n' {lines} | debconf-set-selections")
    chroot_lines += [
        "RC=0",
        f"apt-get update -q && apt-get install -y --no-install-recommends {pkgs} || RC=$?",
        "rm -f /etc/dpkg/dpkg.cfg.d/aft-unsafe-io",
        'exit "$RC"',
    ]
    chroot_cmd = "\n".join(chroot_lines)

    return (
        "export DEBIAN_FRONTEND=noninteractive\n"
        "CAP=/opt/aft-cap\n"
        'mkdir -p "$CAP"\n'
        'if ! mountpoint -q "$CAP"; then\n'
        "  IMG=/var/tmp/aft-cap.img\n"
        f'  if [ ! -f "$IMG" ]; then truncate -s {capture_size_gb}G "$IMG"; mkfs.ext4 -q -F "$IMG"; fi\n'
        '  mount -o loop "$IMG" "$CAP"\n'
        "fi\n"
        'mkdir -p "$CAP/upper" "$CAP/work" "$CAP/merged"\n'
        'mount -t overlay overlay -o "lowerdir=/,upperdir=$CAP/upper,workdir=$CAP/work" "$CAP/merged"\n'
        'for _d in proc sys dev dev/pts run; do mount --bind "/$_d" "$CAP/merged/$_d"; done\n'
        f'chroot "$CAP/merged" /bin/bash -c {shlex.quote(chroot_cmd)}\n'
        'for _d in run dev/pts dev sys proc; do umount "$CAP/merged/$_d" 2>/dev/null || true; done\n'
        'umount "$CAP/merged" 2>/dev/null || true\n'
        "# 휘발성 경로 제거 — 레이어에 포함하지 않음\n"
        'rm -rf "$CAP/upper/tmp" "$CAP/upper/run" "$CAP/upper/var/cache" \\\n'
        '       "$CAP/upper/var/lib/apt/lists" "$CAP/upper/var/log" "$CAP/upper/root" \\\n'
        '       "$CAP/upper/etc/machine-id" 2>/dev/null || true\n' + parallel_copy('"$CAP/upper"', LAYER_ROOT)
    )


# ---------------------------------------------------------------------------
# squashfs 레이어 빌드 블록
# ---------------------------------------------------------------------------


def squashfs_uv_layer(name: str) -> str:
    """uv 바이너리만 담은 squashfs 레이어를 빌드하는 스크립트.

    NFS share(/mnt/share)에 다음을 기록한다:
      /mnt/share/images/<name>-<ts>.sqsh          — squashfs 이미지
      /mnt/share/images/<name>-latest.sqsh        — 최신 심링크

    consumer VM에서 layer-activate.sh가 loop-mount + OverlayFS로 합성한다.
    /usr/local/bin/uv 만 포함 (CPython 미포함).
    """
    _validate([name], _LAYER_NAME_RE, "레이어 이름")
    output_dir = f"{LAYER_ROOT}/images"
    quoted_name = shlex.quote(name)

    script = uv_bootstrap()
    script += (
        'STAGING="$(mktemp -d /tmp/layer-staging.XXXXX)"\n'
        'LAYER_TS="$(date +%Y%m%d%H%M%S)"\n'
        f'LAYER_VERSION={quoted_name}-"$LAYER_TS"\n'
        'STAGING_BINDIR="$STAGING/usr/local/bin"\n'
        'mkdir -p "$STAGING_BINDIR"\n'
        "# uv 바이너리만 포함 (CPython 제외)\n"
        'cp -a /usr/local/bin/uv "$STAGING_BINDIR/uv"\n'
    )
    script += (
        f"mkdir -p {output_dir}\n"
        f'OUT_SQSH={output_dir}/"$LAYER_VERSION.sqsh"\n'
        'mksquashfs "$STAGING" "$OUT_SQSH" -comp zstd -Xcompression-level 3 -noappend -no-exports\n'
        f'ln -sf "$LAYER_VERSION.sqsh" {output_dir}/{quoted_name}-latest.sqsh\n'
        'rm -rf "$STAGING"\n'
    )
    return script


def squashfs_system_apt_layer(name: str, apt_packages: list[str], *, capture_size_gb: int = 8) -> str:
    """apt 패키지 변경분을 캡처해 admin workflow squashfs 이미지로 기록한다."""
    _validate([name], _LAYER_NAME_RE, "레이어 이름")
    if not apt_packages:
        raise ValueError("apt_packages가 비어 있습니다")
    _validate(apt_packages, _APT_NAME_RE, "apt 패키지명")
    if not (1 <= capture_size_gb <= 64):
        raise ValueError(f"capture_size_gb 범위 초과: {capture_size_gb}")

    pkgs = " ".join(shlex.quote(pkg) for pkg in apt_packages)
    output_dir = f"{LAYER_ROOT}/images"
    quoted_name = shlex.quote(name)
    chroot_cmd = "\n".join(
        [
            "export DEBIAN_FRONTEND=noninteractive",
            "mkdir -p /etc/dpkg/dpkg.cfg.d",
            "echo force-unsafe-io > /etc/dpkg/dpkg.cfg.d/aft-unsafe-io",
            "RC=0",
            f"apt-get update -q && apt-get install -y --no-install-recommends {pkgs} || RC=$?",
            "rm -f /etc/dpkg/dpkg.cfg.d/aft-unsafe-io",
            'exit "$RC"',
        ]
    )

    return (
        "set -euo pipefail\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "CAP=/opt/aft-cap\n"
        "cleanup_overlay() {\n"
        '  for _d in run dev/pts dev sys proc; do umount "$CAP/merged/$_d" 2>/dev/null || true; done\n'
        '  umount "$CAP/merged" 2>/dev/null || true\n'
        "}\n"
        "cleanup_all() {\n"
        "  cleanup_overlay\n"
        '  umount "$CAP" 2>/dev/null || true\n'
        "}\n"
        "trap cleanup_all EXIT\n"
        'mkdir -p "$CAP"\n'
        'if ! mountpoint -q "$CAP"; then\n'
        "  IMG=/var/tmp/aft-cap.img\n"
        f'  if [ ! -f "$IMG" ]; then truncate -s {capture_size_gb}G "$IMG"; mkfs.ext4 -q -F "$IMG"; fi\n'
        '  mount -o loop "$IMG" "$CAP"\n'
        "fi\n"
        'mkdir -p "$CAP/upper" "$CAP/work" "$CAP/merged"\n'
        'mount -t overlay overlay -o "lowerdir=/,upperdir=$CAP/upper,workdir=$CAP/work" "$CAP/merged"\n'
        'for _d in proc sys dev dev/pts run; do mkdir -p "$CAP/merged/$_d"; mount --bind "/$_d" "$CAP/merged/$_d"; done\n'
        f'chroot "$CAP/merged" /bin/bash -c {shlex.quote(chroot_cmd)}\n'
        "cleanup_overlay\n"
        "# 휘발성 경로 제거 — 레이어에 포함하지 않음\n"
        'rm -rf "$CAP/upper/tmp" "$CAP/upper/run" "$CAP/upper/var/cache" \\\n'
        '       "$CAP/upper/var/lib/apt/lists" "$CAP/upper/var/log" "$CAP/upper/root" \\\n'
        '       "$CAP/upper/etc/machine-id" 2>/dev/null || true\n'
        'LAYER_TS="$(date +%Y%m%d%H%M%S)"\n'
        f'LAYER_VERSION={quoted_name}-"$LAYER_TS"\n'
        f"mkdir -p {output_dir}\n"
        f'OUT_SQSH={output_dir}/"$LAYER_VERSION.sqsh"\n'
        'mksquashfs "$CAP/upper" "$OUT_SQSH" -comp zstd -Xcompression-level 3 -noappend -no-exports\n'
        f'ln -sf "$LAYER_VERSION.sqsh" {output_dir}/{quoted_name}-latest.sqsh\n'
    )


def squashfs_nvidia_driver_layer(name: str, driver_branch: str = "580") -> str:
    """Consumer-boot NVIDIA compute driver installer hook layer.

    The layer payload is deliberately /usr-rooted because the default consumer
    activation overlays only <sqsh>/usr onto /usr. DKMS builds run on the
    consumer VM via the activation hook so linux-headers-$(uname -r), depmod,
    and module installation match the consumer kernel, not the builder kernel.
    """
    _validate([name], _LAYER_NAME_RE, "레이어 이름")
    if not re.match(r"^\d{3}$", driver_branch) or driver_branch not in _NVIDIA_DRIVER_BRANCH_VALUES:
        allowed = ", ".join(sorted(_NVIDIA_DRIVER_BRANCH_VALUES))
        raise ValueError(f"지원하지 않는 NVIDIA 드라이버 브랜치: {driver_branch!r} (allowed: {allowed})")

    quoted_name = shlex.quote(name)
    quoted_branch = shlex.quote(driver_branch)
    output_dir = f"{LAYER_ROOT}/images"
    hook_script = f"""#!/usr/bin/env bash
set -euo pipefail

BRANCH={quoted_branch}
MARKER="/var/lib/afterglow/nvidia-driver-${{BRANCH}}.done"

if [ -f "$MARKER" ] && command -v nvidia-smi >/dev/null 2>&1; then
  echo "[afterglow-nvidia] NVIDIA driver branch $BRANCH already installed"
  exit 0
fi

if [ ! -r /etc/os-release ]; then
  echo "[afterglow-nvidia] /etc/os-release not found" >&2
  exit 1
fi
. /etc/os-release
if [ "${{ID:-}}" != "ubuntu" ]; then
  echo "[afterglow-nvidia] unsupported OS ID: ${{ID:-unknown}}" >&2
  exit 1
fi
DISTRO="ubuntu${{VERSION_ID//./}}"
ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64) CUDA_ARCH="x86_64" ;;
  arm64) CUDA_ARCH="sbsa" ;;
  *)
    echo "[afterglow-nvidia] unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

TMP="$(mktemp -d /tmp/afterglow-nvidia.XXXXXX)"
cleanup() {{ rm -rf "$TMP"; }}
trap cleanup EXIT

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y --no-install-recommends ca-certificates curl gnupg
cd "$TMP"
curl -fsSLO "https://developer.download.nvidia.com/compute/cuda/repos/${{DISTRO}}/${{CUDA_ARCH}}/cuda-keyring_1.1-1_all.deb"
dpkg -i cuda-keyring_1.1-1_all.deb
apt-get update -q
apt-get install -y --no-install-recommends \\
  "linux-headers-$(uname -r)" \\
  dkms \\
  kmod \\
  "nvidia-dkms-${{BRANCH}}-open" \\
  "libnvidia-compute-${{BRANCH}}" \\
  "nvidia-utils-${{BRANCH}}"
depmod "$(uname -r)"
mkdir -p /var/lib/afterglow
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$MARKER"
echo "[afterglow-nvidia] installed NVIDIA driver branch $BRANCH for kernel $(uname -r)"
"""
    hook_b64 = base64.b64encode(hook_script.encode()).decode()

    return (
        "set -euo pipefail\n"
        'STAGING="$(mktemp -d /tmp/layer-staging.XXXXX)"\n'
        'cleanup() { rm -rf "$STAGING"; }\n'
        "trap cleanup EXIT\n"
        'LAYER_TS="$(date +%Y%m%d%H%M%S)"\n'
        f'LAYER_VERSION={quoted_name}-"$LAYER_TS"\n'
        'HOOK_DIR="$STAGING/usr/lib/afterglow/layer-hooks.d"\n'
        'MANIFEST_DIR="$STAGING/usr/share/afterglow/layers"\n'
        'mkdir -p "$HOOK_DIR" "$MANIFEST_DIR"\n'
        f"base64 -d > \"$HOOK_DIR/50-nvidia-driver-install.sh\" <<'AFTERGLOW_NVIDIA_HOOK'\n{hook_b64}\nAFTERGLOW_NVIDIA_HOOK\n"
        'chmod 0755 "$HOOK_DIR/50-nvidia-driver-install.sh"\n'
        f"cat > \"$MANIFEST_DIR/{name}-nvidia-driver.txt\" <<'EOF'\n"
        "kind=nvidia\n"
        f"driver_branch={driver_branch}\n"
        "install_phase=consumer-boot\n"
        f"packages=ca-certificates,curl,gnupg,linux-headers-$(uname -r),dkms,kmod,nvidia-dkms-{driver_branch}-open,libnvidia-compute-{driver_branch},nvidia-utils-{driver_branch}\n"
        "overlay_contract=/usr-only activation hook\n"
        "EOF\n"
        'if find "$STAGING" -mindepth 1 -maxdepth 1 ! -name usr | grep -q .; then\n'
        '  echo "[afterglow-nvidia] internal error: non-/usr payload generated" >&2\n'
        '  find "$STAGING" -mindepth 1 -maxdepth 2 >&2\n'
        "  exit 1\n"
        "fi\n"
        f"mkdir -p {output_dir}\n"
        f'OUT_SQSH={output_dir}/"$LAYER_VERSION.sqsh"\n'
        'mksquashfs "$STAGING" "$OUT_SQSH" -comp zstd -Xcompression-level 3 -noappend -no-exports\n'
        f'ln -sf "$LAYER_VERSION.sqsh" {output_dir}/{quoted_name}-latest.sqsh\n'
    )


def squashfs_python_layer(name: str, python_version: str) -> str:
    """uv standalone CPython만 담은 squashfs 레이어를 빌드하는 스크립트.

    NFS share(/mnt/share)에 다음을 기록한다:
      /mnt/share/images/<name>-<ts>.sqsh          — squashfs 이미지
      /mnt/share/images/<name>-latest.sqsh        — 최신 심링크

    uv 바이너리는 포함하지 않는다 (squashfs_uv_layer로 별도 레이어 빌드).
    프로필(.conf) 기록도 하지 않는다 — LayerProfile DB가 담당.
    """
    _validate([name], _LAYER_NAME_RE, "레이어 이름")
    _validate([python_version], _PY_VERSION_RE, "Python 버전")
    v = python_version
    output_dir = f"{LAYER_ROOT}/images"
    quoted_name = shlex.quote(name)

    # uv 설치(빌드 전용) + CPython 설치
    script = uv_bootstrap() + _resolve_uv_python(v)

    # staging: CPython 트리만 (uv 바이너리 제외)
    script += (
        'STAGING="$(mktemp -d /tmp/layer-staging.XXXXX)"\n'
        'LAYER_TS="$(date +%Y%m%d%H%M%S)"\n'
        f'LAYER_VERSION={quoted_name}-"$LAYER_TS"\n'
        'STAGING_LOCAL="$STAGING/usr/local"\n'
        'mkdir -p "$STAGING_LOCAL"\n'
        "# CPython 트리만 복사 (uv 바이너리 제외 — 별도 레이어)\n"
        'cp -a "$PYDIR/." "$STAGING_LOCAL/"\n'
    )

    script += (
        f"mkdir -p {output_dir}\n"
        f'OUT_SQSH={output_dir}/"$LAYER_VERSION.sqsh"\n'
        'mksquashfs "$STAGING" "$OUT_SQSH" -comp zstd -Xcompression-level 3 -noappend -no-exports\n'
        f'ln -sf "$LAYER_VERSION.sqsh" {output_dir}/{quoted_name}-latest.sqsh\n'
        'rm -rf "$STAGING"\n'
    )
    return script


def squashfs_stacked_layer(
    name: str,
    python_version: str | None,
    pip_packages: list[str] | None,
    parent_exports: list[tuple[str, str]],
    pip_index_url: str | None = None,
    pip_extra_index_urls: list[str] | None = None,
    pip_find_links: list[str] | None = None,
) -> str:
    """부모 레이어 체인을 빌드 VM에 RO 마운트하고 delta만 squash하는 stacked 빌드 스크립트.

    부모 체인의 share들을 NFS RO로 순서대로 마운트하고 OverlayFS로 합성한 뒤,
    그 위에서 패키지/python을 설치하고 delta(upper dir)만 새 레이어 share에 기록한다.

    Args:
        name:           빌드할 레이어 이름 ([a-z0-9][a-z0-9.+-]*).
        python_version: CPython 버전 (major.minor). 설정 시 부모의 uv로 CPython을 설치.
        pip_packages:   pip 패키지 스펙 목록. 부모 python으로 설치.
        parent_exports: 조상 체인 [(export_path, sqsh_filename), ...].
        pip_index_url: pip install --index-url 값. http(s), credential/query/fragment 불허.
        pip_extra_index_urls: pip install --extra-index-url 값 목록.
        pip_find_links: pip install --find-links 값 목록.
                        index 0 = 직계 부모(스택 최상위), index -1 = 베이스.
                        export_path: Manila NFS export 경로 (예: 10.0.0.1:/path).
                        sqsh_filename: 해당 share의 /images/ 아래 .sqsh 파일명.

    비어 있는 parent_exports는 허용하지 않는다 — 부모 없는 레이어는 squashfs_uv_layer /
    squashfs_python_layer를 사용할 것.
    """
    if not parent_exports:
        raise ValueError(
            "parent_exports는 비어 있을 수 없습니다. "
            "부모 없는 레이어는 squashfs_uv_layer 또는 squashfs_python_layer를 사용하세요."
        )
    _validate([name], _LAYER_NAME_RE, "레이어 이름")
    if python_version:
        _validate([python_version], _PY_VERSION_RE, "Python 버전")
    if pip_packages:
        _validate(pip_packages, _PIP_SPEC_RE, "pip 패키지 스펙")

    # Manila 반환 동적값 검증 (신뢰하지 않음)
    for export_path, sqsh_filename in parent_exports:
        if not _NFS_EXPORT_RE.match(export_path):
            raise ValueError(f"유효하지 않은 NFS export 경로: {export_path!r}")
        if "\n" in export_path or "\r" in export_path:
            raise ValueError("NFS export 경로에 개행 문자 불허")
        if not _SQSH_FILENAME_RE.match(sqsh_filename):
            raise ValueError(f"유효하지 않은 sqsh 파일명: {sqsh_filename!r}")

    output_dir = f"{LAYER_ROOT}/images"
    quoted_name = shlex.quote(name)
    n = len(parent_exports)

    parent_dir_list = " ".join(f"/mnt/parent/{i}" for i in range(n))
    lower_dir_list = " ".join(f"/mnt/lower/{i}" for i in range(n))

    script = "set -euo pipefail\n"
    script += f"mkdir -p {parent_dir_list} {lower_dir_list} /mnt/upper /mnt/work /mnt/merged\n"

    # EXIT trap — 마운트를 역순으로 해제 (실패 시에도 정리)
    umount_parts = ["umount /mnt/merged 2>/dev/null || true"]
    for i in range(n):
        umount_parts.append(f"umount /mnt/lower/{i} 2>/dev/null || true")
        umount_parts.append(f"umount /mnt/parent/{i} 2>/dev/null || true")
    trap_body = "; ".join(umount_parts)
    script += f"trap '{trap_body}' EXIT\n"

    # 부모 share NFS 마운트 → squashfs loop-mount (index 0 = 직계 부모)
    for i, (export_path, sqsh_filename) in enumerate(parent_exports):
        q_export = shlex.quote(export_path)
        q_sqsh = shlex.quote(sqsh_filename)
        script += (
            f"mount -t nfs4 -o ro,hard,timeo=50,retrans=3 {q_export} /mnt/parent/{i}\n"
            f"mount -t squashfs -o ro /mnt/parent/{i}/images/{q_sqsh} /mnt/lower/{i}\n"
        )

    # OverlayFS 합성: lowerdir 최좌측(index 0) = 스택 최상위
    lower_colon = ":".join(f"/mnt/lower/{i}" for i in range(n))
    script += f"mount -t overlay overlay -o lowerdir={lower_colon},upperdir=/mnt/upper,workdir=/mnt/work /mnt/merged\n"

    # CPython 설치 (kind=python, parent=uv 레이어)
    if python_version:
        pv = shlex.quote(python_version)
        minor = python_version.split(".", 1)[1] if "." in python_version else python_version
        script += (
            f"PY_VER={pv}\n"
            "# 부모 레이어의 uv 바이너리 사용; 없으면 자체 bootstrap\n"
            "UV_BIN=/mnt/merged/usr/local/bin/uv\n"
            'if [ ! -x "$UV_BIN" ]; then\n'
            "  curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh\n"
            "  UV_BIN=/usr/local/bin/uv\n"
            "fi\n"
            '"$UV_BIN" python install "$PY_VER"\n'
            'PYDIR=$("$UV_BIN" python find "$PY_VER" | xargs dirname | xargs dirname)\n'
            f'PYBIN="$PYDIR/bin/python3.{minor}"\n'
            "# CPython 트리를 upper(delta)에 복사\n"
            "mkdir -p /mnt/upper/usr/local\n"
            'cp -a "$PYDIR/." /mnt/upper/usr/local/\n'
        )
    else:
        # pip 전용: 부모 merged view에서 실제 python3.x 인터프리터 탐색.
        # python3.11-config 같은 helper는 uv --python 대상이 아니므로 제외하고,
        # 직접 실행 검증까지 통과한 후보만 사용한다.
        if pip_packages:
            script += (
                "UV_BIN=/mnt/merged/usr/local/bin/uv\n"
                'PYBIN=""\n'
                "while IFS= read -r candidate; do\n"
                "  if \"$candidate\" -c 'import sys' >/dev/null 2>&1; then\n"
                '    PYBIN="$candidate"\n'
                "  fi\n"
                "done < <(find /mnt/merged/usr/local/bin -maxdepth 1 \\( -type f -o -type l \\) "
                "-executable -name 'python3.[0-9]*' ! -name '*-config' | sort -V)\n"
                'if [ -z "$PYBIN" ]; then\n'
                '  echo "[ERROR] 부모 레이어에서 실행 가능한 python3 인터프리터를 찾을 수 없습니다" >&2\n'
                "  exit 1\n"
                "fi\n"
            )

    # pip 패키지 설치 — OverlayFS copy-up으로 /mnt/upper에 기록
    if pip_packages:
        pkgs = " ".join(shlex.quote(p) for p in pip_packages)
        source_args = _pip_source_args(pip_index_url, pip_extra_index_urls, pip_find_links)
        source_args = f" {source_args}" if source_args else ""
        script += (
            f'"$UV_BIN" pip install --python "$PYBIN" --system --break-system-packages --no-cache{source_args} {pkgs}\n'
        )

    # delta(upper)를 squash → 새 레이어 share(/mnt/share/images/)에 기록
    script += (
        'LAYER_TS="$(date +%Y%m%d%H%M%S)"\n'
        f'LAYER_VERSION={quoted_name}-"$LAYER_TS"\n'
        f"mkdir -p {output_dir}\n"
        f'OUT_SQSH={output_dir}/"$LAYER_VERSION.sqsh"\n'
        'mksquashfs /mnt/upper "$OUT_SQSH" -comp zstd -Xcompression-level 3 -noappend -no-exports\n'
        f'ln -sf "$LAYER_VERSION.sqsh" {output_dir}/{quoted_name}-latest.sqsh\n'
    )
    return script
