#!/usr/bin/env bash
# build-layer-diff.sh — OverlayFS diff 캡처 → squashfs 레이어 빌드 (apt 패키지용)
#
# 사용법: build-layer-diff.sh <layer-name> <package1> [package2 ...]
# 예시:   build-layer-diff.sh nginx nginx
#         build-layer-diff.sh devtools git curl wget build-essential
#
# 동작:
#   1. 루프백 ext4 이미지 생성 (/var/tmp/aft-cap.img) → upper/work 용 격리 FS 확보
#      NFS는 overlayfs upperdir 불가, lowerdir=/ 와 같은 FS 는 overlap 제한 → ext4 필수
#   2. OverlayFS(lowerdir=/ upper=ext4) merged chroot 에서 apt-get install
#      → 변경분(diff)이 upper에만 격리 기록됨
#   3. upper 에서 휘발성 경로·whiteout 제거 후 squashfs(zstd) 압축 출력
#
# uv 기반 Python 레이어는 build-uv-python-layer.sh 를 사용하세요.
# 이 스크립트는 nginx·cuda·build-essential 등 apt 시스템 패키지 전용입니다.
#
# 환경변수:
#   OUTPUT_DIR      — 출력 경로 (기본: /srv/layers/images)
#   CAPTURE_SIZE_GB — ext4 이미지 크기 GB (기본: 8, 최대: 64)
#
# 빌드 머신: Ubuntu 24.04, root 권한 필요
# 필수: squashfs-tools, e2fsprogs (mkfs.ext4)

set -euo pipefail

# ---------------------------------------------------------------------------
# 인자 검증 (화이트리스트 — 명령 주입 방어)
# ---------------------------------------------------------------------------
if [ $# -lt 2 ]; then
    echo "사용법: $0 <layer-name> <package1> [package2 ...]" >&2
    echo "예시:   $0 nginx nginx" >&2
    echo "        $0 devtools git curl wget build-essential" >&2
    exit 1
fi

# 화이트리스트: Debian 패키지/레이어 이름 정책 (^[a-z0-9][a-z0-9.+-]*$)
_validate_name() {
    local val="$1" kind="$2"
    if ! [[ "$val" =~ ^[a-z0-9][a-z0-9.+\-]*$ ]]; then
        echo "오류: 유효하지 않은 ${kind}: '${val}'" >&2
        echo "      소문자·숫자·점(.)·더하기(+)·하이픈(-) 만 허용됩니다." >&2
        exit 1
    fi
}

LAYER_NAME="$1"
shift
_validate_name "$LAYER_NAME" "layer-name"

PACKAGES=("$@")
for _pkg in "${PACKAGES[@]}"; do
    _validate_name "$_pkg" "package"
done

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
OUTPUT_DIR="${OUTPUT_DIR:-/srv/layers/images}"
CAPTURE_SIZE_GB="${CAPTURE_SIZE_GB:-8}"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
VERSION="${LAYER_NAME}-${TIMESTAMP}"
LOG_FILE="/var/log/build-layer-${LAYER_NAME}.log"

# 루프백 ext4: upper/work 용 격리 FS (NFS/overlap 제한 회피)
CAP=/opt/aft-cap
IMG=/var/tmp/aft-cap.img

# merged 는 /tmp 에서 OK (loop mount 종료 후 rm)
MERGE="$(mktemp -d /tmp/layer-merge.XXXXX)"

echo "=== 레이어 빌드 시작: ${VERSION} ===" | tee "$LOG_FILE"
echo "=== 패키지: ${PACKAGES[*]} ===" | tee -a "$LOG_FILE"
echo "=== 출력: ${OUTPUT_DIR}/${VERSION}.sqsh ===" | tee -a "$LOG_FILE"

mkdir -p "$OUTPUT_DIR"

# ---------------------------------------------------------------------------
# 정리 trap — 역순 umount 보장
# ---------------------------------------------------------------------------
_cleanup() {
    local rc=$?
    echo "[cleanup] 마운트 정리 중 (rc=${rc})" | tee -a "$LOG_FILE"
    # chroot bind mount 역순 해제
    umount "${MERGE}/etc/resolv.conf" 2>/dev/null || true
    umount "${MERGE}/dev/pts"         2>/dev/null || true
    umount "${MERGE}/dev"             2>/dev/null || true
    umount "${MERGE}/sys"             2>/dev/null || true
    umount "${MERGE}/proc"            2>/dev/null || true
    # overlay merged 해제
    umount "${MERGE}"                 2>/dev/null || true
    # 루프백 ext4 해제 (upper/work FS)
    umount "${CAP}"                   2>/dev/null || true
    rm -rf "${MERGE}" 2>/dev/null || true
    echo "[cleanup] 완료" | tee -a "$LOG_FILE"
}
trap _cleanup EXIT

# ---------------------------------------------------------------------------
# overlay 커널 모듈 로드
# ---------------------------------------------------------------------------
modprobe overlay 2>/dev/null || true

# ---------------------------------------------------------------------------
# 1. 루프백 ext4 이미지 준비 — upper/work 용 격리 FS
#    lowerdir=/ 와 같은 파일시스템에 upper 를 두면 overlayfs 가 overlap 오류 발생
#    → sparse ext4 이미지를 loop mount 해 완전히 분리된 FS 사용 (멱등)
# ---------------------------------------------------------------------------
echo "[build] ext4 캡처 이미지 준비: ${IMG}" | tee -a "$LOG_FILE"
mkdir -p "$CAP"
if ! mountpoint -q "$CAP"; then
    if [ ! -f "$IMG" ]; then
        truncate -s "${CAPTURE_SIZE_GB}G" "$IMG"
        mkfs.ext4 -q -F "$IMG"
        echo "[build] ext4 이미지 생성: ${CAPTURE_SIZE_GB}GB sparse" | tee -a "$LOG_FILE"
    fi
    mount -o loop "$IMG" "$CAP"
fi

# upper/work 초기화 (누적된 이전 빌드 잔재 제거)
rm -rf "${CAP}/upper" "${CAP}/work"
mkdir -p "${CAP}/upper" "${CAP}/work"
mkdir -p "${MERGE}"

# ---------------------------------------------------------------------------
# 2. OverlayFS(lowerdir=/) 설정 — diff 캡처 시작
# ---------------------------------------------------------------------------
echo "[build] OverlayFS 구성: lowerdir=/ upperdir=${CAP}/upper" | tee -a "$LOG_FILE"
mount -t overlay overlay \
    -o "lowerdir=/,upperdir=${CAP}/upper,workdir=${CAP}/work" \
    "${MERGE}"

# chroot 에 필요한 가상 파일시스템 bind mount
mount --bind /proc             "${MERGE}/proc"
mount --bind /sys              "${MERGE}/sys"
mount --bind /dev              "${MERGE}/dev"
mount --bind /dev/pts          "${MERGE}/dev/pts"
mount --bind /etc/resolv.conf  "${MERGE}/etc/resolv.conf"

# ---------------------------------------------------------------------------
# 3. merged chroot 에서 apt 설치 (변경분은 upper 에만 기록됨)
# ---------------------------------------------------------------------------
echo "[build] 패키지 설치: ${PACKAGES[*]}" | tee -a "$LOG_FILE"
DEBIAN_FRONTEND=noninteractive \
    chroot "${MERGE}" /bin/bash -c "
        set -e
        mkdir -p /etc/dpkg/dpkg.cfg.d
        echo force-unsafe-io > /etc/dpkg/dpkg.cfg.d/aft-unsafe-io
        apt-get update -q
        apt-get install -y --no-install-recommends ${PACKAGES[*]}
        apt-get clean
        rm -f /etc/dpkg/dpkg.cfg.d/aft-unsafe-io
    " 2>&1 | tee -a "$LOG_FILE"

# ---------------------------------------------------------------------------
# 4. bind mount + overlay 역순 해제
# ---------------------------------------------------------------------------
umount "${MERGE}/etc/resolv.conf"
umount "${MERGE}/dev/pts"
umount "${MERGE}/dev"
umount "${MERGE}/sys"
umount "${MERGE}/proc"
umount "${MERGE}"

# ---------------------------------------------------------------------------
# 5. upper 정리 — whiteout·런타임 캐시 제거
#    .wh.*        = 파일 삭제 마커
#    .wh..wh..opq = opaque 마커 (디렉토리 전체 대체)
#    → 레이어에는 순수 추가·변경분만 남긴다
# ---------------------------------------------------------------------------
echo "[build] whiteout 및 런타임 캐시 제거..." | tee -a "$LOG_FILE"
find "${CAP}/upper" -name '.wh.*'                   -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/var/cache/apt/*"       -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/var/lib/apt/lists/*"   -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/var/log/*"             -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/tmp/*"                 -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/etc/machine-id"        -delete 2>/dev/null || true
find "${CAP}/upper" -path "*/root/*"                -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 6. squashfs 생성 (zstd level-3)
# ---------------------------------------------------------------------------
echo "[build] squashfs 생성: ${OUTPUT_DIR}/${VERSION}.sqsh" | tee -a "$LOG_FILE"
mksquashfs "${CAP}/upper" "${OUTPUT_DIR}/${VERSION}.sqsh" \
    -comp zstd \
    -Xcompression-level 3 \
    -noappend \
    -no-exports \
    2>&1 | tee -a "$LOG_FILE"

# ext4 해제 (trap 에서도 재시도하므로 이중 안전)
umount "${CAP}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 7. latest 심링크 갱신
# ---------------------------------------------------------------------------
ln -sf "${VERSION}.sqsh" "${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh"

echo "" | tee -a "$LOG_FILE"
echo "=== 빌드 완료 ===" | tee -a "$LOG_FILE"
ls -lh "${OUTPUT_DIR}/${VERSION}.sqsh" | tee -a "$LOG_FILE"
echo "심링크: ${OUTPUT_DIR}/${LAYER_NAME}-latest.sqsh → ${VERSION}.sqsh" | tee -a "$LOG_FILE"
