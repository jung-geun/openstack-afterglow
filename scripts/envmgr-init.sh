#!/bin/bash
# envmgr-init.sh — User VM cloud-init 통합 스크립트
# Manila RO share(layer-store-ro) 마운트 + envmgr-use 설치
#
# 환경변수 (cloud-init write_files로 주입):
#   LAYER_STORE_RO_EXPORT  — Manila CephFS export 경로 (예: 172.30.0.5:6789:/volumes/_nogroup/abc123)
#   AFTERGLOW_API_URL      — Afterglow API 베이스 URL
#   AFTERGLOW_API_TOKEN    — API 인증 토큰
#   CEPH_KEYRING_PATH      — CephX keyring 파일 경로 (기본: /etc/ceph/ceph.client.union.keyring)

set -euo pipefail

LAYER_STORE_RO_MOUNT="${LAYER_STORE_RO_MOUNT:-/mnt/layer-store-ro}"
CEPH_KEYRING_PATH="${CEPH_KEYRING_PATH:-/etc/ceph/ceph.client.union.keyring}"
ENVMGR_USE_PATH="/usr/local/bin/envmgr-use"
OVERLAY_BASE="/var/overlay"

echo "==> envmgr-init: 시작"

# 1. 마운트 포인트 생성
mkdir -p "${LAYER_STORE_RO_MOUNT}" "${OVERLAY_BASE}"

# 2. CephFS 커널 클라이언트로 RO share 마운트
if [ -z "${LAYER_STORE_RO_EXPORT:-}" ]; then
    echo "경고: LAYER_STORE_RO_EXPORT 미설정 — 레이어 스토어 마운트 생략"
else
    echo "==> layer-store-ro 마운트: ${LAYER_STORE_RO_EXPORT} → ${LAYER_STORE_RO_MOUNT}"

    MOUNT_OPTS="ro,_netdev,noatime"
    if [ -f "${CEPH_KEYRING_PATH}" ]; then
        # CephX 인증 사용
        CEPH_SECRET=$(grep -oP '(?<=key = ).*' "${CEPH_KEYRING_PATH}" | tr -d ' ')
        MOUNT_OPTS="${MOUNT_OPTS},secret=${CEPH_SECRET}"
    fi

    mount -t ceph "${LAYER_STORE_RO_EXPORT}" "${LAYER_STORE_RO_MOUNT}" \
        -o "${MOUNT_OPTS}" || {
        echo "오류: CephFS 마운트 실패. NFS 폴백 시도..."
        mount -t nfs -o ro,_netdev "${LAYER_STORE_RO_EXPORT}" "${LAYER_STORE_RO_MOUNT}"
    }

    echo "==> layer-store-ro 마운트 완료"
fi

# 3. envmgr-use 스크립트 설치
cat > "${ENVMGR_USE_PATH}" << 'ENVMGR_USE_SCRIPT'
#!/bin/bash
# envmgr-use — Union Mount 환경 활성화 스크립트 (User VM용)
# Usage: envmgr-use <layer_id|sha256:hash>
#        envmgr-use --template <name>@<version>
#        envmgr-use --unmount
# 설치: /usr/local/bin/envmgr-use (envmgr-init.sh이 자동 설치)

ENVMGR_USE_SCRIPT

# envmgr-use 본문을 별도 파일로 복사 (아래 heredoc은 실제 envmgr-use.sh 내용)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/envmgr-use.sh" ]; then
    cp "${SCRIPT_DIR}/envmgr-use.sh" "${ENVMGR_USE_PATH}"
else
    # cloud-init으로 직접 실행 시 스크립트가 없을 수 있음 — 최소 버전 사용
    echo '#!/bin/bash' > "${ENVMGR_USE_PATH}"
    echo 'echo "오류: envmgr-use.sh를 찾을 수 없습니다. 수동으로 설치하세요."' >> "${ENVMGR_USE_PATH}"
    echo 'exit 1' >> "${ENVMGR_USE_PATH}"
fi
chmod +x "${ENVMGR_USE_PATH}"

# 4. 환경변수 파일 생성 (/etc/envmgr.conf)
cat > /etc/envmgr.conf << EOF
# envmgr 설정 — envmgr-init.sh이 자동 생성
AFTERGLOW_API_URL="${AFTERGLOW_API_URL:-}"
AFTERGLOW_API_TOKEN="${AFTERGLOW_API_TOKEN:-}"
LAYER_STORE_RO_MOUNT="${LAYER_STORE_RO_MOUNT}"
OVERLAY_BASE="${OVERLAY_BASE}"
EOF

# 5. systemd unit 등록 (부팅 시 자동 마운트)
if [ -n "${LAYER_STORE_RO_EXPORT:-}" ]; then
    cat > /etc/systemd/system/layer-store-ro.mount << EOF
[Unit]
Description=Union Mount Layer Store RO
After=network-online.target
Wants=network-online.target
DefaultDependencies=no

[Mount]
What=${LAYER_STORE_RO_EXPORT}
Where=${LAYER_STORE_RO_MOUNT}
Type=ceph
Options=ro,_netdev,noatime

[Install]
WantedBy=remote-fs.target
EOF
    systemctl daemon-reload
    systemctl enable layer-store-ro.mount || true
fi

echo "==> envmgr-init: 완료"
echo "==> 사용법: envmgr-use <layer_id> 또는 envmgr-use --template <name>@<ver>"
