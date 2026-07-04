#!/usr/bin/env bash
# build-layer.sh — debootstrap minbase + chroot apt → squashfs (대안 방식)
#
# 사용법: build-layer.sh <layer-name> <package1> [package2 ...]
# 예시:   build-layer.sh python3 python3 python3-pip
#
# 동작:
#   1. debootstrap으로 Ubuntu 24.04 noble minbase rootfs 생성
#   2. chroot에서 패키지 설치
#   3. 전체 rootfs를 squashfs(zstd)로 압축 (boot 제외)
#
# 이 방식은 완전한 최소 Ubuntu rootfs를 기반으로 하므로 호스트 오염이 없지만,
# debootstrap 시간(수 분)이 걸린다.
# 변경분(diff)만 빠르게 캡처하려면 build-layer-diff.sh 를 사용한다.
#
# 빌드 머신: Ubuntu 24.04, root 권한 필요
# 필수 패키지: debootstrap, squashfs-tools
#
# 환경변수:
#   OUTPUT_DIR    — 출력 경로 (기본: /srv/layers/images)
#   UBUNTU_MIRROR — apt mirror (기본: http://archive.ubuntu.com/ubuntu)

set -euo pipefail

# ---------------------------------------------------------------------------
# 인자 검증
# ---------------------------------------------------------------------------
if [ $# -lt 2 ]; then
    echo "사용법: $0 <layer-name> <package1> [package2 ...]" >&2
    echo "예시:   $0 python3 python3 python3-pip" >&2
    exit 1
fi

# 화이트리스트: 명령 주입 방어
_validate_name() {
    local val="$1" kind="$2"
    if ! [[ "$val" =~ ^[a-z0-9][a-z0-9.+\-]*$ ]]; then
        echo "오류: 유효하지 않은 ${kind}: '${val}'" >&2
        exit 1
    fi
}

LAYER_NAME="$1"
shift
_validate_name "$LAYER_NAME" "layer-name"
PACKAGES=("$@")
for pkg in "${PACKAGES[@]}"; do
    _validate_name "$pkg" "package"
done

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
OUTPUT_DIR="${OUTPUT_DIR:-/srv/layers/images}"
UBUNTU_MIRROR="${UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
VERSION="${LAYER_NAME}-${TIMESTAMP}"
BUILD_ROOT="$(mktemp -d /tmp/layer-build.XXXXX)"
LOG_FILE="/var/log/build-layer-${LAYER_NAME}.log"

echo "=== debootstrap 레이어 빌드: ${VERSION} ===" | tee "$LOG_FILE"
echo "=== 패키지: ${PACKAGES[*]} ===" | tee -a "$LOG_FILE"

mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# 정리 trap
# ---------------------------------------------------------------------------
_cleanup() {
    local rc=$?
    echo "[cleanup] 정리 중 (rc=${rc})" | tee -a "$LOG_FILE"
    umount "${BUILD_ROOT}/etc/resolv.conf" 2>/dev/null || true
    umount "${BUILD_ROOT}/dev"             2>/dev/null || true
    umount "${BUILD_ROOT}/sys"             2>/dev/null || true
    umount "${BUILD_ROOT}/proc"            2>/dev/null || true
    rm -rf "${BUILD_ROOT}" 2>/dev/null || true
    echo "[cleanup] 완료" | tee -a "$LOG_FILE"
}
trap _cleanup EXIT

# ---------------------------------------------------------------------------
# 1. debootstrap — Ubuntu 24.04 noble, minbase (최소 패키지만)
# ---------------------------------------------------------------------------
echo "[build] debootstrap noble minbase → ${BUILD_ROOT}" | tee -a "$LOG_FILE"
debootstrap --variant=minbase noble "$BUILD_ROOT" "$UBUNTU_MIRROR" \
    2>&1 | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 2. 가상 파일시스템 bind mount
# ---------------------------------------------------------------------------
mount --bind /proc            "${BUILD_ROOT}/proc"
mount --bind /sys             "${BUILD_ROOT}/sys"
mount --bind /dev             "${BUILD_ROOT}/dev"
mount --bind /etc/resolv.conf "${BUILD_ROOT}/etc/resolv.conf"

# ---------------------------------------------------------------------------
# 3. chroot에서 패키지 설치
# ---------------------------------------------------------------------------
echo "[build] 패키지 설치: ${PACKAGES[*]}" | tee -a "$LOG_FILE"
DEBIAN_FRONTEND=noninteractive chroot "$BUILD_ROOT" \
    apt-get update -q 2>&1 | tee -a "$LOG_FILE"
DEBIAN_FRONTEND=noninteractive chroot "$BUILD_ROOT" \
    apt-get install -y --no-install-recommends "${PACKAGES[@]}" 2>&1 | tee -a "$LOG_FILE"
DEBIAN_FRONTEND=noninteractive chroot "$BUILD_ROOT" \
    apt-get clean 2>&1 | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 4. bind mount 역순 해제
# ---------------------------------------------------------------------------
umount "${BUILD_ROOT}/etc/resolv.conf"
umount "${BUILD_ROOT}/dev"
umount "${BUILD_ROOT}/sys"
umount "${BUILD_ROOT}/proc"

# 불필요한 캐시/임시 파일 정리
rm -rf "${BUILD_ROOT}/var/lib/apt/lists/"*
rm -rf "${BUILD_ROOT}/var/cache/apt/"*
rm -rf "${BUILD_ROOT}/tmp/"*

# ---------------------------------------------------------------------------
# 5. squashfs 생성
# ---------------------------------------------------------------------------
echo "[build] squashfs 생성: ${OUTPUT_DIR}/${VERSION}.sqsh" | tee -a "$LOG_FILE"
mksquashfs "$BUILD_ROOT" "${OUTPUT_DIR}/${VERSION}.sqsh" \
    -comp zstd \
    -Xcompression-level 3 \
    -noappend \
    -no-exports \
    -e boot \
    2>&1 | tee -a "$LOG_FILE"

ln -sf "${VERSION}.sqsh" "${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh"

echo "" | tee -a "$LOG_FILE"
echo "=== 빌드 완료 ===" | tee -a "$LOG_FILE"
ls -lh "${OUTPUT_DIR}/${VERSION}.sqsh" | tee -a "$LOG_FILE"
