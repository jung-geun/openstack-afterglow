#!/usr/bin/env bash
# layer-activate.sh — squashfs 레이어 마운트 + OverlayFS 합성 (VM 측)
#
# 사용법: layer-activate.sh <profile-name>
# 예시:   layer-activate.sh ml-worker
#
# 동작:
#   1. $NFS_MOUNT/profiles/<profile>.conf 에서 레이어 목록 읽기
#   2. 각 레이어 .sqsh를 loop mount (RO), 로컬 캐시 fallback 포함
#   3. lowerdir 체인 + 베이스 / 로 OverlayFS 합성
#   4. $OVERLAY_TARGET 에 overlay 마운트
#
# 환경변수:
#   NFS_MOUNT       — Manila NFS share 마운트 경로 (기본: /mnt/nfs-layers)
#   SQSH_BASE       — squashfs loop mount 베이스 디렉토리 (기본: /mnt/sqsh)
#   CACHE_DIR       — 로컬 squashfs 캐시 (기본: /var/cache/layers)
#   LOCAL_UPPER     — overlay upperdir, 재부팅 후에도 유지됨 (기본: /var/lib/overlay/upper)
#   LOCAL_WORK      — overlay workdir (기본: /var/lib/overlay/work)
#   OVERLAY_TARGET  — overlay 마운트 대상 (기본: /usr)
#
# /usr overlay 주의:
#   런타임에 /usr 위에 overlay를 마운트하면 이미 실행 중인 프로세스에는 적용되지 않습니다.
#   systemd 서비스 Before=multi-user.target 으로 충분히 이르게 실행하면 모든 사용자
#   서비스가 새 /usr 를 봅니다. 재부팅이 가장 안전합니다.
#   대안: OVERLAY_TARGET=/opt/layers/merged 처럼 전용 경로를 쓰고 PATH/PYTHONPATH 조정.

set -euo pipefail

# ---------------------------------------------------------------------------
# 인자 검증
# ---------------------------------------------------------------------------
if [ $# -ne 1 ]; then
    echo "사용법: $0 <profile-name>" >&2
    echo "예시:   $0 ml-worker" >&2
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

PROFILE="$1"
_validate_name "$PROFILE" "profile-name"

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
NFS_MOUNT="${NFS_MOUNT:-/mnt/nfs-layers}"
SQSH_BASE="${SQSH_BASE:-/mnt/sqsh}"
CACHE_DIR="${CACHE_DIR:-/var/cache/layers}"
LOCAL_UPPER="${LOCAL_UPPER:-/var/lib/overlay/upper}"
LOCAL_WORK="${LOCAL_WORK:-/var/lib/overlay/work}"
OVERLAY_TARGET="${OVERLAY_TARGET:-/usr}"

LOG="/var/log/layer-activate.log"
exec >> "$LOG" 2>&1
echo "[$(date)] layer-activate 시작: profile=${PROFILE} target=${OVERLAY_TARGET}"

# ---------------------------------------------------------------------------
# 디렉토리 준비
# ---------------------------------------------------------------------------
mkdir -p "$SQSH_BASE" "$CACHE_DIR" "$LOCAL_UPPER" "$LOCAL_WORK"
_layer_lowerdir() {
    local mount_point="$1"
    if [ "$OVERLAY_TARGET" = "/usr" ]; then
        local lower="${mount_point}/usr"
        if [ ! -d "$lower" ]; then
            echo "[ERROR] /usr lowerdir 없음: ${lower}" >&2
            exit 1
        fi
        printf '%s\n' "$lower"
    else
        printf '%s\n' "$mount_point"
    fi
}


# ---------------------------------------------------------------------------
# 1. 프로필 읽기
# ---------------------------------------------------------------------------
PROFILE_FILE="${NFS_MOUNT}/profiles/${PROFILE}.conf"
if [ ! -f "$PROFILE_FILE" ]; then
    echo "[ERROR] 프로필 파일 없음: ${PROFILE_FILE}" >&2
    exit 1
fi

# 주석·빈 줄 제거 + 이름 검증
LAYERS=()
while IFS= read -r line; do
    line="${line%%#*}"        # inline 주석 제거
    line="${line//[[:space:]]/}"  # 공백 제거
    [ -z "$line" ] && continue
    _validate_name "$line" "layer (in profile)"
    LAYERS+=("$line")
done < "$PROFILE_FILE"

if [ "${#LAYERS[@]}" -eq 0 ]; then
    echo "[ERROR] 프로필 '${PROFILE}' 에 유효한 레이어가 없습니다." >&2
    exit 1
fi

echo "[$(date)] 레이어 목록: ${LAYERS[*]}"

# ---------------------------------------------------------------------------
# 2. 각 레이어 squashfs 마운트 (로컬 캐시 fallback 포함)
#    - NFS 접근 가능 시 캐시를 최신 상태로 동기화
#    - 캐시 우선 마운트 → NFS 장애 시에도 동작
# ---------------------------------------------------------------------------
LOWER_DIRS=""

for LAYER in "${LAYERS[@]}"; do
    SQSH_NFS="${NFS_MOUNT}/images/${LAYER}.sqsh"
    SQSH_CACHE="${CACHE_DIR}/${LAYER}.sqsh"
    MOUNT_POINT="${SQSH_BASE}/${LAYER}"

    # 이미 마운트된 경우 스킵 (멱등, systemctl restart 안전)
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        echo "[$(date)] 이미 마운트됨: ${LAYER} → ${MOUNT_POINT} (스킵)"
        LAYER_LOWER="$(_layer_lowerdir "$MOUNT_POINT")"
        LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${LAYER_LOWER}"
        continue
    fi

    mkdir -p "$MOUNT_POINT"

    # NFS 캐시 동기화: NFS 사용 가능하고 캐시가 없거나 오래됐으면 갱신
    if [ -f "$SQSH_NFS" ]; then
        _nfs_size="$(stat -c%s "$SQSH_NFS" 2>/dev/null || echo 0)"
        _cache_size="$(stat -c%s "$SQSH_CACHE" 2>/dev/null || echo -1)"
        if [ ! -f "$SQSH_CACHE" ] || \
           [ "$SQSH_NFS" -nt "$SQSH_CACHE" ] || \
           [ "$_nfs_size" != "$_cache_size" ]; then
            echo "[$(date)] 캐시 갱신: ${LAYER}"
            cp "$SQSH_NFS" "${SQSH_CACHE}.tmp" 2>/dev/null \
                && mv "${SQSH_CACHE}.tmp" "$SQSH_CACHE" \
                || echo "[경고] 캐시 갱신 실패 (계속 진행)" | tee /dev/stderr
        fi
    fi

    # 마운트 소스 결정: 캐시 우선, 없으면 NFS 직접
    if [ -f "$SQSH_CACHE" ]; then
        SQSH_SRC="$SQSH_CACHE"
        echo "[$(date)] 캐시 사용: ${LAYER}"
    elif [ -f "$SQSH_NFS" ]; then
        SQSH_SRC="$SQSH_NFS"
        echo "[$(date)] NFS 직접 사용: ${LAYER} (캐시 없음)"
    else
        echo "[ERROR] 레이어 이미지 없음 (NFS·캐시 모두): ${LAYER}" >&2
        echo "        NFS_MOUNT=${NFS_MOUNT}, CACHE_DIR=${CACHE_DIR}" >&2
        exit 1
    fi

    mount -t squashfs "$SQSH_SRC" "$MOUNT_POINT" -o ro
    echo "[$(date)] 마운트 완료: ${LAYER} → ${MOUNT_POINT}"

    LAYER_LOWER="$(_layer_lowerdir "$MOUNT_POINT")"
    LOWER_DIRS="${LOWER_DIRS:+${LOWER_DIRS}:}${LAYER_LOWER}"
done

# ---------------------------------------------------------------------------
# 3. OverlayFS 합성
#
#    lowerdir: 레이어(먼저 나온 것이 우선순위 높음) : 베이스 /
#    upperdir:  VM 로컬 상위 레이어 (재부팅 후에도 유지)
#    workdir:   OverlayFS 내부 작업 공간 (빈 상태여야 함)
#    metacopy=on: 메타데이터 lazy-copy (커널 6.8+, 성능 향상)
# ---------------------------------------------------------------------------

_run_layer_hooks() {
    local hook_dir
    if [ "$OVERLAY_TARGET" = "/usr" ]; then
        hook_dir="/usr/lib/afterglow/layer-hooks.d"
    else
        hook_dir="${OVERLAY_TARGET}/usr/lib/afterglow/layer-hooks.d"
    fi
    if [ ! -d "$hook_dir" ]; then
        return 0
    fi
    echo "[$(date)] 레이어 hook 실행: ${hook_dir}"
    while IFS= read -r -d '' hook; do
        echo "[$(date)] hook 시작: ${hook}"
        "$hook"
        echo "[$(date)] hook 완료: ${hook}"
    done < <(find "$hook_dir" -maxdepth 1 -type f -name '*.sh' -perm -0100 -print0 | sort -z)
}

# 이미 overlay로 마운트된 경우 스킵
if mountpoint -q "$OVERLAY_TARGET" 2>/dev/null; then
    _fstype="$(findmnt -n -o FSTYPE "$OVERLAY_TARGET" 2>/dev/null || true)"
    if [ "$_fstype" = "overlay" ]; then
        echo "[$(date)] ${OVERLAY_TARGET} 이미 overlay 마운트됨 — hook 재실행 후 스킵"
        _run_layer_hooks
        echo "[$(date)] layer-activate 완료 (이미 활성)"
        exit 0
    fi
fi

# stale workdir 정리 (OverlayFS는 빈 workdir 요구)
if [ -d "$LOCAL_WORK" ]; then
    rm -rf "${LOCAL_WORK:?}/"* "${LOCAL_WORK:?}/".* 2>/dev/null || true
fi

BASE_LOWER="/"
if [ "$OVERLAY_TARGET" = "/usr" ]; then
    BASE_LOWER="${BASE_USR_LOWER:-/run/afterglow/base-usr}"
    mkdir -p "$BASE_LOWER"
    if ! mountpoint -q "$BASE_LOWER" 2>/dev/null; then
        mount --bind /usr "$BASE_LOWER"
    fi
fi

echo "[$(date)] OverlayFS 마운트 시작"
echo "[$(date)]   target  : ${OVERLAY_TARGET}"
echo "[$(date)]   lowerdir: ${LOWER_DIRS}:${BASE_LOWER}"
echo "[$(date)]   upperdir: ${LOCAL_UPPER}"
echo "[$(date)]   workdir : ${LOCAL_WORK}"

mount -t overlay overlay \
    -o "lowerdir=${LOWER_DIRS}:${BASE_LOWER},upperdir=${LOCAL_UPPER},workdir=${LOCAL_WORK},metacopy=on" \
    "$OVERLAY_TARGET"


_run_layer_hooks

echo "[$(date)] OverlayFS 활성화 완료: ${OVERLAY_TARGET}"
echo "[$(date)] 적용된 레이어: ${LAYERS[*]}"
echo "[$(date)] layer-activate 완료"
