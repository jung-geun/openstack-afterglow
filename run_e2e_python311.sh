#!/usr/bin/env bash
# ============================================================
# run_e2e_python311.sh — python 3.11 라이브러리 라이프사이클 E2E
# ============================================================
# 7단계 인수 시나리오를 라이브 OpenStack 인프라에서 실행한다:
#   1. file storage 생성 (Manila)
#   2. 해당 share를 빌더 VM에 연결 → uv로 python 3.11 설치
#   3. cloud-init 완료 → prebuilt 승격 + 빌더 VM/port 자동 teardown
#   4. uv 산출물이 /opt/layers/merged overlayfs로 접근 가능
#   5. 새 consumer VM: python311 prebuilt share RO 마운트
#   6. SSH: python3.11 실제 실행 검증
#   7. consumer VM 정리
#
# 사전 요건:
#   - OpenStack 도달 가능 (172.30.0.253:5000, MariaDB)
#   - config.toml에 OpenStack/DB 설정 완료
#   - AFTERGLOW_TEST_SSH_KEY_NAME이 Nova keypair에 등록되어 있어야 함
#     (기본값 afterglow-e2e-test 는 이미 등록 완료)
#
# 사용법:
#   ./run_e2e_python311.sh
#   AFTERGLOW_TEST_IMAGE_ID=<uuid> AFTERGLOW_TEST_FLAVOR_SMALL=<uuid> ./run_e2e_python311.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# ── 기본값 ──────────────────────────────────────────────────
# ubuntu-24.04-2026-04-28
: "${AFTERGLOW_TEST_IMAGE_ID:=9390745d-69b3-42ec-a5b1-28800b653bdd}"
# cpu.4c_4g  (4vCPU / 4GB RAM)
: "${AFTERGLOW_TEST_FLAVOR_SMALL:=1bb05535-afff-4034-b95f-4b3d55a1b8b8}"
# ed25519 키 (./run_e2e_python311.sh 실행 전 ssh-keygen으로 생성됨)
: "${AFTERGLOW_TEST_SSH_KEY:=$HOME/.ssh/afterglow-e2e}"
: "${AFTERGLOW_TEST_SSH_USER:=ubuntu}"
# 빌드 타임아웃 (초) — uv python install ≈ 5분 + cloud-init
: "${AFTERGLOW_TEST_BUILD_TIMEOUT:=2400}"
: "${AFTERGLOW_TEST_VM_TIMEOUT:=600}"

# ── 출력 ────────────────────────────────────────────────────
echo "=================================================="
echo " Afterglow python 3.11 라이프사이클 E2E"
echo "=================================================="
echo "  IMAGE_ID     : $AFTERGLOW_TEST_IMAGE_ID"
echo "  FLAVOR_SMALL : $AFTERGLOW_TEST_FLAVOR_SMALL"
echo "  SSH_KEY      : $AFTERGLOW_TEST_SSH_KEY"
echo "  SSH_USER     : $AFTERGLOW_TEST_SSH_USER"
echo "  BUILD_TIMEOUT: ${AFTERGLOW_TEST_BUILD_TIMEOUT}s"
echo "=================================================="
echo ""

# SSH 키 파일 검증
if [[ ! -f "$AFTERGLOW_TEST_SSH_KEY" ]]; then
    echo "ERROR: SSH 개인 키가 없습니다: $AFTERGLOW_TEST_SSH_KEY"
    echo "  다음 명령으로 생성하세요:"
    echo "    ssh-keygen -t ed25519 -f ~/.ssh/afterglow-e2e -N ''"
    exit 1
fi
chmod 600 "$AFTERGLOW_TEST_SSH_KEY"

# ── pytest 실행 ──────────────────────────────────────────────
cd "$BACKEND_DIR"
export AFTERGLOW_ALLOW_INSECURE=1
export AFTERGLOW_TEST_IMAGE_ID
export AFTERGLOW_TEST_FLAVOR_SMALL
export AFTERGLOW_TEST_SSH_KEY
export AFTERGLOW_TEST_SSH_USER
export AFTERGLOW_TEST_BUILD_TIMEOUT
export AFTERGLOW_TEST_VM_TIMEOUT

exec uv run pytest \
    tests/integration/test_python311_lifecycle_e2e.py \
    -m slow \
    -v \
    --tb=short \
    -s \
    "$@"
