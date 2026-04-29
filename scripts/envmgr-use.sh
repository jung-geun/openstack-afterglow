#!/bin/bash
# envmgr-use — Union Mount 환경 활성화 스크립트 (User VM용)
#
# Usage:
#   envmgr-use <layer_id>              # sha256:... 레이어 직접 지정
#   envmgr-use --template <name>@<ver> # 템플릿으로 활성화
#   envmgr-use --unmount               # 현재 환경 비활성화
#   envmgr-use --status                # 현재 마운트 상태 표시
#
# 설정: /etc/envmgr.conf (envmgr-init.sh이 생성)

set -euo pipefail

# ---------------------------------------------------------------------------
# 설정 로드
# ---------------------------------------------------------------------------

if [ -f /etc/envmgr.conf ]; then
    # shellcheck disable=SC1091
    source /etc/envmgr.conf
fi

AFTERGLOW_API_URL="${AFTERGLOW_API_URL:-}"
AFTERGLOW_API_TOKEN="${AFTERGLOW_API_TOKEN:-}"
LAYER_STORE_RO_MOUNT="${LAYER_STORE_RO_MOUNT:-/mnt/layer-store-ro}"
OVERLAY_BASE="${OVERLAY_BASE:-/var/overlay}"
MOUNT_POINT="/mnt/env"

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_die() { echo "오류: $*" >&2; exit 1; }

_api_get() {
    local path="$1"
    local url="${AFTERGLOW_API_URL}${path}"
    curl -s -f -H "Authorization: Bearer ${AFTERGLOW_API_TOKEN}" "${url}" \
        || _die "API 호출 실패: ${url}"
}

_layer_diff_path() {
    local layer_id="$1"
    local hash_hex="${layer_id#sha256:}"
    echo "${LAYER_STORE_RO_MOUNT}/sha256-${hash_hex}/diff"
}

_check_layer_exists() {
    local diff_path="$1"
    local layer_id="$2"
    if [ ! -d "${diff_path}" ]; then
        _die "레이어 diff 디렉토리 없음: ${diff_path}\n레이어 ${layer_id}가 로컬 스토어에 동기화되지 않았습니다."
    fi
}

# ---------------------------------------------------------------------------
# 서브커맨드: mount (기본)
# ---------------------------------------------------------------------------

_do_mount() {
    local leaf_id="$1"

    [ -z "${AFTERGLOW_API_URL}" ] && _die "AFTERGLOW_API_URL이 설정되지 않았습니다 (/etc/envmgr.conf 확인)"
    [ -z "${AFTERGLOW_API_TOKEN}" ] && _die "AFTERGLOW_API_TOKEN이 설정되지 않았습니다"

    echo "==> 조상 체인 조회: ${leaf_id}"
    local chain
    chain=$(_api_get "/api/union/layers/${leaf_id}/ancestors")

    # JSON 파싱 (jq 또는 python3 사용)
    local layer_ids=()
    if command -v jq &>/dev/null; then
        mapfile -t layer_ids < <(echo "${chain}" | jq -r '.layers[].id')
    elif command -v python3 &>/dev/null; then
        mapfile -t layer_ids < <(echo "${chain}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for l in data['layers']:
    print(l['id'])
")
    else
        _die "jq 또는 python3가 필요합니다"
    fi

    if [ ${#layer_ids[@]} -eq 0 ]; then
        _die "조상 체인이 비어 있습니다"
    fi

    echo "==> 레이어 체인 (base-first): ${layer_ids[*]}"

    # 각 레이어 diff 디렉토리 존재 확인
    local diff_paths=()
    for lid in "${layer_ids[@]}"; do
        local diff_path
        diff_path=$(_layer_diff_path "${lid}")
        _check_layer_exists "${diff_path}" "${lid}"
        diff_paths+=("${diff_path}")
    done

    # lowerdir 조립: 최신(leaf)이 leftmost
    # layer_ids는 base-first이므로 역순으로 lowerdir 조립
    local lowerdir=""
    for (( i=${#diff_paths[@]}-1; i>=0; i-- )); do
        if [ -n "${lowerdir}" ]; then
            lowerdir="${lowerdir}:${diff_paths[$i]}"
        else
            lowerdir="${diff_paths[$i]}"
        fi
    done

    # upperdir/workdir 생성 (로컬 디스크)
    local hash_hex="${leaf_id#sha256:}"
    local overlay_dir="${OVERLAY_BASE}/${hash_hex}"
    local upper="${overlay_dir}/upper"
    local work="${overlay_dir}/work"

    mkdir -p "${upper}" "${work}" "${MOUNT_POINT}"

    # 기존 마운트 해제
    if mountpoint -q "${MOUNT_POINT}"; then
        echo "==> 기존 마운트 해제: ${MOUNT_POINT}"
        umount "${MOUNT_POINT}"
    fi

    # overlay 마운트
    echo "==> overlay 마운트: ${MOUNT_POINT}"
    mount -t overlay overlay \
        -o "lowerdir=${lowerdir},upperdir=${upper},workdir=${work}" \
        "${MOUNT_POINT}"

    # 현재 상태 저장
    echo "${leaf_id}" > "${OVERLAY_BASE}/.current_layer"

    # 마운트 기록 (best-effort: 실패해도 마운트 자체는 유지)
    if [ -n "${AFTERGLOW_API_URL}" ] && [ -n "${AFTERGLOW_API_TOKEN}" ] && command -v jq &>/dev/null; then
        local vm_hostname
        vm_hostname=$(hostname -s 2>/dev/null || echo "unknown")
        local mount_body
        mount_body=$(jq -n --arg lid "${leaf_id}" --arg h "${vm_hostname}" \
            '{"leaf_layer_id": $lid, "vm_hostname": $h}')
        local mount_resp
        mount_resp=$(curl -s --max-time 5 -X POST \
            -H "Authorization: Bearer ${AFTERGLOW_API_TOKEN}" \
            -H "Content-Type: application/json" \
            -d "${mount_body}" \
            "${AFTERGLOW_API_URL}/api/union/mounts" 2>/dev/null || true)
        local mount_id
        mount_id=$(echo "${mount_resp}" | jq -r '.id // empty' 2>/dev/null || true)
        if [ -n "${mount_id}" ]; then
            echo "${mount_id}" > "${OVERLAY_BASE}/.current_mount_id"
        fi
    fi

    echo "==> 환경 활성화 완료"
    echo "    마운트 포인트: ${MOUNT_POINT}"
    echo "    레이어: ${leaf_id}"
    echo "    체인 깊이: ${#layer_ids[@]}개"
    echo ""
    echo "==> 사용하려면: export PATH=\"${MOUNT_POINT}/usr/local/bin:\$PATH\""
}

# ---------------------------------------------------------------------------
# 서브커맨드: template
# ---------------------------------------------------------------------------

_do_template() {
    local template_spec="$1"
    local name version

    # "name@version" 파싱
    if [[ "${template_spec}" == *@* ]]; then
        name="${template_spec%%@*}"
        version="${template_spec##*@}"
    else
        _die "템플릿 형식: <name>@<version> (예: ml-pytorch@1)"
    fi

    echo "==> 템플릿 조회: ${name} v${version}"
    local tmpl_info
    tmpl_info=$(_api_get "/api/union/templates")

    local leaf_id
    if command -v jq &>/dev/null; then
        leaf_id=$(echo "${tmpl_info}" | jq -r --arg n "${name}" --arg v "${version}" \
            '.[] | select(.name==$n and (.version|tostring)==$v) | .leaf_layer_id' | head -1)
    elif command -v python3 &>/dev/null; then
        leaf_id=$(echo "${tmpl_info}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data:
    if t['name'] == '${name}' and str(t['version']) == '${version}':
        print(t['leaf_layer_id'])
        break
")
    else
        _die "jq 또는 python3가 필요합니다"
    fi

    [ -z "${leaf_id}" ] && _die "템플릿을 찾을 수 없습니다: ${template_spec}"
    echo "==> leaf 레이어: ${leaf_id}"
    _do_mount "${leaf_id}"
}

# ---------------------------------------------------------------------------
# 서브커맨드: unmount
# ---------------------------------------------------------------------------

_do_unmount() {
    # 마운트 해제 기록 (best-effort)
    if [ -n "${AFTERGLOW_API_URL}" ] && [ -n "${AFTERGLOW_API_TOKEN}" ] && [ -f "${OVERLAY_BASE}/.current_mount_id" ]; then
        local mount_id
        mount_id=$(cat "${OVERLAY_BASE}/.current_mount_id")
        curl -s --max-time 5 -X POST \
            -H "Authorization: Bearer ${AFTERGLOW_API_TOKEN}" \
            "${AFTERGLOW_API_URL}/api/union/mounts/${mount_id}/unmount" 2>/dev/null || true
        rm -f "${OVERLAY_BASE}/.current_mount_id"
    fi

    if mountpoint -q "${MOUNT_POINT}"; then
        umount "${MOUNT_POINT}"
        echo "==> 환경 비활성화 완료: ${MOUNT_POINT}"
    else
        echo "==> 현재 마운트된 환경이 없습니다"
    fi
    rm -f "${OVERLAY_BASE}/.current_layer"
}

# ---------------------------------------------------------------------------
# 서브커맨드: status
# ---------------------------------------------------------------------------

_do_status() {
    echo "=== envmgr 상태 ==="
    echo "마운트 포인트: ${MOUNT_POINT}"
    if mountpoint -q "${MOUNT_POINT}"; then
        echo "상태: 활성"
        if [ -f "${OVERLAY_BASE}/.current_layer" ]; then
            echo "현재 레이어: $(cat "${OVERLAY_BASE}/.current_layer")"
        fi
        mount | grep "${MOUNT_POINT}"
    else
        echo "상태: 비활성"
    fi
    echo ""
    echo "layer-store-ro: ${LAYER_STORE_RO_MOUNT}"
    if mountpoint -q "${LAYER_STORE_RO_MOUNT}"; then
        echo "스토어 상태: 마운트됨"
    else
        echo "스토어 상태: 마운트 안 됨"
    fi
}

# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

if [ $# -eq 0 ]; then
    echo "사용법:"
    echo "  envmgr-use <layer_id>              # sha256:... 레이어 활성화"
    echo "  envmgr-use --template <name>@<ver> # 템플릿으로 활성화"
    echo "  envmgr-use --unmount               # 환경 비활성화"
    echo "  envmgr-use --status                # 현재 상태 확인"
    exit 0
fi

case "$1" in
    --unmount|-u)
        _do_unmount
        ;;
    --status|-s)
        _do_status
        ;;
    --template|-t)
        [ $# -lt 2 ] && _die "--template 옵션에 <name>@<version>을 지정하세요"
        _do_template "$2"
        ;;
    sha256:*)
        _do_mount "$1"
        ;;
    --help|-h)
        echo "사용법:"
        echo "  envmgr-use <sha256:...>           레이어 직접 지정"
        echo "  envmgr-use --template <name>@<n>  템플릿으로 활성화"
        echo "  envmgr-use --unmount              환경 비활성화"
        echo "  envmgr-use --status               상태 확인"
        ;;
    *)
        _die "알 수 없는 인자: $1 (sha256:... 형식의 레이어 ID 또는 --template <name>@<version> 사용)"
        ;;
esac
