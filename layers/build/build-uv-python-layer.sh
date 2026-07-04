#!/usr/bin/env bash
# build-uv-python-layer.sh — uv 관리 standalone CPython squashfs 레이어 빌드
#
# 사용법: build-uv-python-layer.sh <layer-name> <python-version> [pip-pkg ...]
# 예시:   build-uv-python-layer.sh uvpy311 3.11
#         build-uv-python-layer.sh uvpy311 3.11 numpy scipy
#
# 동작:
#   1. uv 설치 (없을 경우 /usr/local/bin 에 설치, 멱등)
#   2. uv로 standalone CPython 설치 (/opt/aft-uvpy/)
#   3. staging 디렉토리에 CPython + uv 바이너리 배치 (FHS: usr/local/)
#   4. pip 패키지 지정 시 uv pip install → staging site-packages
#   5. staging → squashfs(zstd level-3) 압축 출력
#
# consumer VM은 이 .sqsh 를 loop mount(RO) → OverlayFS lowerdir 로 합성하면
# /usr/local/bin/python3.X, /usr/local/bin/uv 를 직접 사용 가능.
# recipe_blocks.python_layer / pip_layer 를 독립 셸 스크립트로 미러링한 것.
#
# 환경변수:
#   OUTPUT_DIR      — 출력 경로 (기본: /srv/layers/images)
#   UV_INSTALL_DIR  — uv 바이너리 설치 경로 (기본: /usr/local/bin)
#   UV_PYTHON_DIR   — uv CPython 설치 디렉토리 (기본: /opt/aft-uvpy)
#
# 빌드 머신: Ubuntu 24.04, root 권한 필요
# 필수: squashfs-tools, curl

set -euo pipefail

# ---------------------------------------------------------------------------
# 인자 검증 (화이트리스트 — 명령 주입 방어)
# ---------------------------------------------------------------------------
if [ $# -lt 2 ]; then
    echo "사용법: $0 <layer-name> <python-version> [pip-pkg ...]" >&2
    echo "예시:   $0 uvpy311 3.11" >&2
    echo "        $0 uvpy311 3.11 numpy scipy" >&2
    exit 1
fi

# 레이어 이름: Debian 패키지명 정책 (소문자·숫자·점·+·-)
_validate_name() {
    local val="$1" kind="$2"
    if ! [[ "$val" =~ ^[a-z0-9][a-z0-9.+\-]*$ ]]; then
        echo "오류: 유효하지 않은 ${kind}: '${val}'" >&2
        echo "      소문자·숫자·점(.)·더하기(+)·하이픈(-) 만 허용됩니다." >&2
        exit 1
    fi
}

# Python 버전: major.minor 형식만 허용
_validate_version() {
    local ver="$1"
    if ! [[ "$ver" =~ ^[0-9]+\.[0-9]+$ ]]; then
        echo "오류: 유효하지 않은 Python 버전: '${ver}' (예: 3.11, 3.12)" >&2
        exit 1
    fi
}

# pip 패키지 스펙: 이름[extras]제약 — 공백·셸 메타문자 불허
_validate_pip_spec() {
    local spec="$1"
    if ! [[ "$spec" =~ ^[A-Za-z0-9][A-Za-z0-9._\[\],\<\>=\!\~\+\*\-]*$ ]]; then
        echo "오류: 유효하지 않은 pip 패키지 스펙: '${spec}'" >&2
        exit 1
    fi
}

LAYER_NAME="$1"
PYTHON_VERSION="$2"
shift 2

_validate_name "$LAYER_NAME" "layer-name"
_validate_version "$PYTHON_VERSION"

PIP_PACKAGES=("$@")
for _pkg in "${PIP_PACKAGES[@]}"; do
    _validate_pip_spec "$_pkg"
done

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
OUTPUT_DIR="${OUTPUT_DIR:-/srv/layers/images}"
UV_INSTALL_DIR="${UV_INSTALL_DIR:-/usr/local/bin}"
UV_PYTHON_DIR="${UV_PYTHON_DIR:-/opt/aft-uvpy}"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
VERSION="${LAYER_NAME}-${TIMESTAMP}"
STAGING="$(mktemp -d /tmp/layer-staging.XXXXX)"
LOG_FILE="/var/log/build-layer-${LAYER_NAME}.log"

echo "=== uv-python 레이어 빌드 시작: ${VERSION} ===" | tee "$LOG_FILE"
echo "=== Python 버전: ${PYTHON_VERSION} ===" | tee -a "$LOG_FILE"
if [ "${#PIP_PACKAGES[@]}" -gt 0 ]; then
    echo "=== pip 패키지: ${PIP_PACKAGES[*]} ===" | tee -a "$LOG_FILE"
fi
echo "=== 출력: ${OUTPUT_DIR}/${VERSION}.sqsh ===" | tee -a "$LOG_FILE"

mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# 정리 trap
# ---------------------------------------------------------------------------
_cleanup() {
    local rc=$?
    [ "$rc" -ne 0 ] && echo "[cleanup] 오류 발생 (rc=${rc})" | tee -a "$LOG_FILE"
    rm -rf "${STAGING}" 2>/dev/null || true
    echo "[cleanup] 완료" | tee -a "$LOG_FILE"
}
trap _cleanup EXIT

# ---------------------------------------------------------------------------
# 1. uv 설치 (멱등 — 이미 있으면 스킵)
# ---------------------------------------------------------------------------
export PATH="${UV_INSTALL_DIR}:${PATH}"

if ! command -v uv >/dev/null 2>&1; then
    echo "[build] uv 설치 중 (${UV_INSTALL_DIR})..." | tee -a "$LOG_FILE"
    curl -LsSf https://astral.sh/uv/install.sh \
        | UV_INSTALL_DIR="${UV_INSTALL_DIR}" sh 2>&1 | tee -a "$LOG_FILE"
    export PATH="${UV_INSTALL_DIR}:${PATH}"
fi
echo "[build] uv $(uv --version)" | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 2. uv standalone CPython 설치 + 실제 경로 해석
#    uv 는 cpython-X.Y (symlink) → cpython-X.Y.Z-linux-... (실제 dir) 구조
# ---------------------------------------------------------------------------
echo "[build] CPython ${PYTHON_VERSION} 설치 (uv)..." | tee -a "$LOG_FILE"
uv python install "cpython-${PYTHON_VERSION}" \
    --install-dir "${UV_PYTHON_DIR}" 2>&1 | tee -a "$LOG_FILE"

PYDIR=""
for _d in "${UV_PYTHON_DIR}/cpython-${PYTHON_VERSION}"*; do
    PYDIR="$(readlink -f "$_d")"
    break
done

if [ -z "$PYDIR" ] || [ ! -d "$PYDIR" ]; then
    echo "[ERROR] uv CPython ${PYTHON_VERSION} 디렉토리 미발견:" >&2
    echo "        패턴: ${UV_PYTHON_DIR}/cpython-${PYTHON_VERSION}*" >&2
    ls "${UV_PYTHON_DIR}/" 2>&1 | head -10 >&2
    exit 1
fi

PYBIN="${PYDIR}/bin/python${PYTHON_VERSION}"
if [ ! -x "$PYBIN" ]; then
    echo "[ERROR] python${PYTHON_VERSION} 실행 파일 미발견: ${PYBIN}" >&2
    ls "${PYDIR}/bin/" 2>&1 | head -10 >&2
    exit 1
fi

echo "[build] CPython 경로: ${PYDIR}" | tee -a "$LOG_FILE"
echo "[build] 실행 파일: ${PYBIN}" | tee -a "$LOG_FILE"
echo "[build] 버전: $(${PYBIN} --version 2>&1)" | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 3. staging 트리 구성 (FHS: usr/local/)
#    consumer VM 에서 OverlayFS lowerdir 로 합성 시 /usr/local/ 로 노출됨
# ---------------------------------------------------------------------------
STAGING_USRLOCAL="${STAGING}/usr/local"
mkdir -p "${STAGING_USRLOCAL}"

echo "[build] CPython → staging/usr/local/ 복사 중..." | tee -a "$LOG_FILE"
# CPython 디렉토리 전체를 staging/usr/local/ 하위에 복사 (재배치 가능)
cp -a "${PYDIR}/." "${STAGING_USRLOCAL}/"

# uv 바이너리도 레이어에 포함 (consumer 가 uv·python 둘 다 사용 가능)
UV_BIN="${UV_INSTALL_DIR}/uv"
if [ -x "$UV_BIN" ]; then
    mkdir -p "${STAGING_USRLOCAL}/bin"
    cp -a "$UV_BIN" "${STAGING_USRLOCAL}/bin/uv"
    echo "[build] uv 바이너리 포함: ${UV_BIN} → staging/usr/local/bin/uv" | tee -a "$LOG_FILE"
fi

# site-packages 디렉토리 보장
SITE="${STAGING_USRLOCAL}/lib/python${PYTHON_VERSION}/site-packages"
mkdir -p "$SITE"

# ---------------------------------------------------------------------------
# 4. pip 패키지 설치 (지정된 경우)
#    uv pip install --target 은 pip 패키지를 SITE 디렉토리에 직접 설치
# ---------------------------------------------------------------------------
if [ "${#PIP_PACKAGES[@]}" -gt 0 ]; then
    echo "[build] pip 패키지 설치: ${PIP_PACKAGES[*]}" | tee -a "$LOG_FILE"
    # shellcheck disable=SC2068
    uv pip install \
        --python "$PYBIN" \
        --no-cache \
        --target "$SITE" \
        ${PIP_PACKAGES[@]} \
        2>&1 | tee -a "$LOG_FILE"
    echo "[build] pip 설치 완료" | tee -a "$LOG_FILE"
fi

# ---------------------------------------------------------------------------
# 5. squashfs 생성 (zstd level-3 — 빠른 압축·충분한 압축률)
# ---------------------------------------------------------------------------
OUT_SQSH="${OUTPUT_DIR}/${VERSION}.sqsh"
echo "[build] squashfs 생성: ${OUT_SQSH}" | tee -a "$LOG_FILE"
mksquashfs "${STAGING}" "${OUT_SQSH}" \
    -comp zstd \
    -Xcompression-level 3 \
    -noappend \
    -no-exports \
    2>&1 | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 6. latest 심링크 갱신
# ---------------------------------------------------------------------------
ln -sf "${VERSION}.sqsh" "${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh"

echo "" | tee -a "$LOG_FILE"
echo "=== 빌드 완료 ===" | tee -a "$LOG_FILE"
ls -lh "${OUT_SQSH}" | tee -a "$LOG_FILE"
echo "심링크: ${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh → ${VERSION}.sqsh" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "[확인]" | tee -a "$LOG_FILE"
echo "  consumer mount: mount -t squashfs ${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh /mnt/sqsh/${LAYER_NAME} -o ro" | tee -a "$LOG_FILE"
echo "  python 경로:   /opt/layers/merged/usr/local/bin/python${PYTHON_VERSION}" | tee -a "$LOG_FILE"
echo "  uv 경로:       /opt/layers/merged/usr/local/bin/uv" | tee -a "$LOG_FILE"
