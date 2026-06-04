#!/usr/bin/env bash
# scripts/setup-builder-ssh-key.sh
#
# Builder VM SSH 키를 생성하고 k8s secret에 등록한다.
#
# 동작 순서:
#   1. ed25519 SSH 키페어 생성
#   2. OpenStack Nova에 공개키 등록 (afterglow-ephemeral-key)
#   3. config.toml [builder] ssh_private_key 업데이트
#   4. generate_k8s.py → deploy/k8s/secret.yaml 재생성
#   5. kubectl apply -f deploy/k8s/secret.yaml
#
# 사전 요구사항:
#   - openstack CLI (OS_AUTH_URL 등 환경변수 또는 clouds.yaml 설정)
#   - kubectl (k8s 클러스터 접근 설정)
#   - python3 (generate_k8s.py 실행)
#
# 멱등성: 재실행 시 기존 Nova 키페어를 삭제하고 새 키로 교체한다.

set -euo pipefail

KEYPAIR_NAME="afterglow-ephemeral-key"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_TOML="$REPO_ROOT/config.toml"

# config.toml에서 service_project_id 읽기
# _ensure_ephemeral_keypair가 get_service_project_connection() 스코프로 동작하므로
# 키페어는 반드시 admin 유저 + service project 에 등록해야 함
SERVICE_PROJECT_ID=$(python3 -c "
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open('$CONFIG_TOML', 'rb') as f:
    cfg = tomllib.load(f)
print(cfg.get('openstack', {}).get('service_project_id', ''))
" 2>/dev/null || true)

# ─────────────────────────────────────────────────────────────
# 사전 조건 검사
# ─────────────────────────────────────────────────────────────
check_deps() {
    local missing=()
    command -v ssh-keygen &>/dev/null || missing+=("ssh-keygen")
    command -v openstack  &>/dev/null || missing+=("openstack CLI")
    command -v kubectl    &>/dev/null || missing+=("kubectl")
    command -v python3    &>/dev/null || missing+=("python3")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "오류: 다음 도구가 필요합니다: ${missing[*]}" >&2
        exit 1
    fi

    if [[ ! -f "$CONFIG_TOML" ]]; then
        echo "오류: $CONFIG_TOML 파일이 없습니다." >&2
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────
# 1. SSH 키페어 생성
# ─────────────────────────────────────────────────────────────
generate_keypair() {
    TMPDIR=$(mktemp -d)
    KEY_FILE="$TMPDIR/builder.key"
    trap 'rm -rf "$TMPDIR"' EXIT

    echo "[1/5] ed25519 SSH 키페어 생성..."
    ssh-keygen -t ed25519 -C "afterglow-builder" -f "$KEY_FILE" -N "" -q
    PRIVATE_KEY=$(cat "$KEY_FILE")
    PUBLIC_KEY=$(cat "$KEY_FILE.pub")
    echo "      완료"
}

# ─────────────────────────────────────────────────────────────
# 2. Nova 키페어 등록
# ─────────────────────────────────────────────────────────────
register_nova_keypair() {
    # _ensure_ephemeral_keypair는 admin유저 + service project 스코프로 키페어를 조회/생성함.
    # service_project_id가 확인된 경우 --os-project-id로 동일 스코프에 등록.
    local os_project_opt=()
    if [[ -n "${SERVICE_PROJECT_ID:-}" ]]; then
        os_project_opt=(--os-project-id "$SERVICE_PROJECT_ID")
        echo "[2/5] Nova 키페어 등록: $KEYPAIR_NAME (project: $SERVICE_PROJECT_ID)"
    else
        echo "[2/5] Nova 키페어 등록: $KEYPAIR_NAME (service_project_id 미확인 — CLI 기본 스코프 사용)"
    fi

    if openstack "${os_project_opt[@]}" keypair show "$KEYPAIR_NAME" &>/dev/null; then
        echo "      기존 키페어 삭제 중..."
        openstack "${os_project_opt[@]}" keypair delete "$KEYPAIR_NAME"
    fi

    openstack "${os_project_opt[@]}" keypair create \
        --public-key "$KEY_FILE.pub" \
        "$KEYPAIR_NAME" \
        --format value -c name > /dev/null

    echo "      완료"
}

# ─────────────────────────────────────────────────────────────
# 3. config.toml 업데이트
# ─────────────────────────────────────────────────────────────
update_config_toml() {
    echo "[3/5] config.toml ssh_private_key 업데이트..."

    python3 - "$CONFIG_TOML" "$KEY_FILE" <<'PYEOF'
import re
import sys

config_path = sys.argv[1]
key_path = sys.argv[2]

with open(config_path, "r") as f:
    content = f.read()

with open(key_path, "r") as f:
    private_key = f.read().rstrip("\n")

# TOML 멀티라인 기본 문자열: """\n...\n"""
toml_value = '"""\n' + private_key + '\n"""'
new_field = f'ssh_private_key = {toml_value}'

if re.search(r'^ssh_private_key\s*=', content, re.MULTILINE):
    # 기존 값 교체 (멀티라인 포함)
    content = re.sub(
        r'^ssh_private_key\s*=\s*(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\')',
        new_field,
        content,
        flags=re.MULTILINE,
    )
else:
    # ssh_key_path 줄 뒤에 추가
    content = re.sub(
        r'(^ssh_key_path\s*=\s*"[^"]*"\s*)',
        r'\1\n' + new_field + '\n',
        content,
        flags=re.MULTILINE,
    )

with open(config_path, "w") as f:
    f.write(content)

print("      완료")
PYEOF
}

# ─────────────────────────────────────────────────────────────
# 4. k8s 매니페스트 재생성
# ─────────────────────────────────────────────────────────────
generate_manifests() {
    echo "[4/5] k8s 매니페스트 재생성 (generate_k8s.py)..."
    cd "$REPO_ROOT"
    python3 generate_k8s.py
    echo "      완료"
}

# ─────────────────────────────────────────────────────────────
# 5. secret.yaml 적용
# ─────────────────────────────────────────────────────────────
apply_secret() {
    local secret_yaml="$REPO_ROOT/deploy/k8s/secret.yaml"
    echo "[5/5] k8s secret 적용..."

    if [[ ! -f "$secret_yaml" ]]; then
        echo "오류: $secret_yaml 파일이 없습니다. generate_k8s.py를 먼저 실행하세요." >&2
        exit 1
    fi

    kubectl apply -f "$secret_yaml"
    echo ""
    echo "완료!"
    echo "  Nova 키페어 : $KEYPAIR_NAME"
    echo "  k8s secret  : afterglow-secrets (BUILDER_SSH_PRIVATE_KEY)"
    echo "  마운트 경로 : /etc/afterglow/ssh/builder.key"
    echo ""
    echo "다음 단계: pod를 재시작해 새 secret을 반영하세요."
    echo "  kubectl rollout restart deployment/backend -n afterglow"
}

# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
main() {
    echo "=== afterglow Builder SSH 키 설정 ==="
    echo ""

    if [[ -z "${SERVICE_PROJECT_ID:-}" ]]; then
        echo "경고: config.toml에서 service_project_id를 읽지 못했습니다."
        echo "      openstack CLI의 현재 프로젝트 스코프로 키페어를 등록합니다."
        echo "      (admin 유저 + service project 스코프가 맞는지 확인하세요)"
        echo ""
    else
        echo "  service project : $SERVICE_PROJECT_ID"
        echo "  Nova 키페어 등록 유저: openstack CLI 현재 인증 유저 (admin 권장)"
        echo ""
    fi

    check_deps
    generate_keypair
    register_nova_keypair
    update_config_toml
    generate_manifests
    apply_secret
}

main "$@"
