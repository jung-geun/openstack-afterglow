#!/usr/bin/env bash
# deploy.sh — config.toml 기반 k8s 리소스 배포 스크립트
# 사용법: ./deploy.sh [--skip-certmgr] [--dry-run]
set -euo pipefail

CERT_MANAGER_VERSION="v1.17.2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_TOML="${SCRIPT_DIR}/../../config.toml"

SKIP_CERTMGR=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --skip-certmgr) SKIP_CERTMGR=true ;;
    --dry-run)      DRY_RUN=true ;;
  esac
done

# ── 색상 출력 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
step()  { echo -e "\n${CYAN}=== $* ===${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
err()   { echo -e "${RED}✖ $*${NC}" >&2; }

# ── TOML 값 추출 헬퍼 ─────────────────────────────────────────────────────────
toml_get() {
  # toml_get <section> <key> [default]
  local section="$1" key="$2" default="${3:-}"
  python3 - "$CONFIG_TOML" "$section" "$key" "$default" <<'EOF'
import sys, tomllib
path, section, key, default = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    val = data.get(section, {}).get(key, default)
    print(str(val) if val is not None else default)
except Exception as e:
    print(default, file=sys.stderr)
    print(default)
EOF
}

# dry-run kubectl 래퍼
kube() {
  if $DRY_RUN; then
    echo "[dry-run] kubectl $*"
  else
    kubectl "$@"
  fi
}

# ── Phase 0: 검증 ─────────────────────────────────────────────────────────────
step "0. 사전 검증"

if [[ ! -f "$CONFIG_TOML" ]]; then
  err "config.toml 파일을 찾을 수 없음: $CONFIG_TOML"
  exit 1
fi
ok "config.toml 존재: $CONFIG_TOML"

if ! python3 -c "import tomllib" 2>/dev/null; then
  err "Python 3.11+ (tomllib) 필요"
  exit 1
fi
ok "Python3 + tomllib 사용 가능"

if ! kubectl cluster-info &>/dev/null; then
  err "kubectl 클러스터 연결 실패"
  exit 1
fi
ok "kubectl 클러스터 연결 확인"

if $DRY_RUN; then
  warn "DRY-RUN 모드 — kubectl 명령 실행 안 함"
fi

# config.toml 에서 필요한 값 추출
OS_PASSWORD_VAL="$(toml_get openstack password "")"
SECRET_KEY_VAL="$(toml_get app secret_key "")"
GITLAB_SECRET_VAL="$(toml_get gitlab_oidc client_secret "")"
K3S_KEY_VAL="$(toml_get k3s kubeconfig_encryption_key "")"
DB_URL_VAL="$(toml_get database url "")"
PROM_USERNAME_VAL="$(toml_get monitoring prometheus_username "")"
PROM_PASSWORD_VAL="$(toml_get monitoring prometheus_password "")"
SD_TOKEN_VAL="$(toml_get monitoring sd_token "")"

[[ -z "$OS_PASSWORD_VAL" ]]    && warn "[openstack] password 미설정 — afterglow-secrets에 빈 값 주입"
[[ -z "$SECRET_KEY_VAL" ]]     && warn "[app] secret_key 미설정"
[[ -z "$DB_URL_VAL" ]]         && warn "[database] url 미설정"
[[ -z "$SD_TOKEN_VAL" ]]       && warn "[monitoring] sd_token 미설정 — Prometheus SD 비활성화됨"

# ── Phase 1: 네임스페이스 ─────────────────────────────────────────────────────
step "1. 네임스페이스"
kube create namespace afterglow --dry-run=client -o yaml | kube apply -f -

# ── Phase 2: cert-manager ─────────────────────────────────────────────────────
step "2. cert-manager"
if $SKIP_CERTMGR; then
  warn "cert-manager 설치 스킵 (--skip-certmgr)"
elif kubectl get deployment -n cert-manager cert-manager &>/dev/null; then
  ok "cert-manager 이미 설치됨, 스킵"
else
  echo "cert-manager ${CERT_MANAGER_VERSION} 설치 중..."
  kube apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
  if ! $DRY_RUN; then
    echo "cert-manager Pod 준비 대기 중 (최대 3분)..."
    kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=180s
  fi
fi

# ── Phase 3: 정적 YAML 리소스 ────────────────────────────────────────────────
step "3. ClusterIssuer / Traefik / Middleware"
kube apply -f "${SCRIPT_DIR}/cert-manager.yaml" \
           -f "${SCRIPT_DIR}/traefik-config.yaml" \
           -f "${SCRIPT_DIR}/middleware.yaml"

# ── Phase 4: ConfigMap (config.toml 파일 마운트) ──────────────────────────────
step "4. ConfigMap (afterglow-config)"
kube create configmap afterglow-config \
  --from-file=config.toml="$CONFIG_TOML" \
  --namespace=afterglow \
  --dry-run=client -o yaml | kube apply -f -
ok "afterglow-config ConfigMap 갱신 완료"

# ── Phase 5: afterglow-secrets ────────────────────────────────────────────────
step "5. Secret (afterglow-secrets)"
kube create secret generic afterglow-secrets \
  --namespace=afterglow \
  --from-literal=OS_PASSWORD="${OS_PASSWORD_VAL}" \
  --from-literal=SECRET_KEY="${SECRET_KEY_VAL}" \
  --from-literal=GITLAB_OIDC_CLIENT_SECRET="${GITLAB_SECRET_VAL}" \
  --from-literal=K3S_KUBECONFIG_ENCRYPTION_KEY="${K3S_KEY_VAL}" \
  --from-literal=DATABASE_URL="${DB_URL_VAL}" \
  --from-literal=PROMETHEUS_USERNAME="${PROM_USERNAME_VAL}" \
  --from-literal=PROMETHEUS_PASSWORD="${PROM_PASSWORD_VAL}" \
  --dry-run=client -o yaml | kube apply -f -
ok "afterglow-secrets 갱신 완료"

# ── Phase 6: Prometheus SD 토큰 Secret ───────────────────────────────────────
step "6. Secret (prometheus-sd-token)"
kube create secret generic prometheus-sd-token \
  --namespace=afterglow \
  --from-literal=sd-token="${SD_TOKEN_VAL}" \
  --dry-run=client -o yaml | kube apply -f -
ok "prometheus-sd-token 갱신 완료"

# ── Phase 7: Ingress ──────────────────────────────────────────────────────────
step "7. Ingress"
kube apply -f "${SCRIPT_DIR}/ingress.yaml"

# ── Phase 8: 모니터링 리소스 ─────────────────────────────────────────────────
step "8. 모니터링 리소스"
kube apply -f "${SCRIPT_DIR}/monitoring/"

# ── 완료 ──────────────────────────────────────────────────────────────────────
step "완료"
if ! $DRY_RUN; then
  echo ""
  echo "비정상 Pod 목록:"
  kubectl get pods --all-namespaces | grep -v -E "Running|Completed|NAME" || true
fi
ok "배포 완료"
