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

import re
import shlex

LAYER_ROOT = "/mnt/share"

# ---------------------------------------------------------------------------
# 입력 검증 (화이트리스트)
# ---------------------------------------------------------------------------

# Debian 패키지명 정책: 소문자 영숫자 시작, [a-z0-9.+-]
_APT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")
# pip 패키지 스펙: 이름[extras]제약 — 공백·셸 메타문자 불허
_PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\[\],<>=!~+*-]*$")
# Python 버전: major.minor
_PY_VERSION_RE = re.compile(r"^\d+\.\d+$")
# debconf 셀렉션 라인: "패키지 키 타입 값"
_DEBCONF_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]* [A-Za-z0-9/._-]+ [a-z]+ [^\n\r]*$")


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
