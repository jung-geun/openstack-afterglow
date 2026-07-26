#!/usr/bin/env bash
# ArgoCD Application values 업데이트 스크립트
#
# helm/afterglow/values-<env>.yaml 변경 후 실행하면 Application CR의 valuesObject가
# 갱신됩니다. afterglow-config/afterglow-secrets의 data는 관리자 직접 적용 영역이므로
# generate_k8s.py 출력물을 kubectl apply 한 뒤 rollout restart 해야 합니다.
#
# 사용법:
#   ./deploy/argocd-sync.sh dev [--dry-run] [--wait]
#
# 차트/템플릿 변경은 git push origin dev 만으로 ArgoCD가 자동 감지합니다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PYTHON="$REPO_ROOT/backend/.venv/bin/python"

ENV="${1:-}"
shift || true

DRY_RUN=""
WAIT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="1"; shift ;;
    --wait)    WAIT="1"; shift ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]] || [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "사용법: $0 <dev|prod> [--dry-run] [--wait]" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "가상환경이 없습니다: $VENV_PYTHON" >&2
  echo "  → cd backend && uv sync" >&2
  exit 1
fi

APP_YAML="$REPO_ROOT/deploy/k8s/argocd-application-$ENV.yaml"
KUBECONFIG="${KUBECONFIG:-$REPO_ROOT/deploy/k8s/kubeconfig}"

echo "▶ ArgoCD Application 생성 중 ($ENV)"
"$VENV_PYTHON" "$REPO_ROOT/argocd/generate_helm_application.py" "$ENV"

if [[ -n "$DRY_RUN" ]]; then
  echo ""
  echo "── dry-run: 생성된 Application CR 미리보기 ──"
  cat "$APP_YAML"
  echo ""
  echo "✓ dry-run 완료 — 실제 적용하려면 --dry-run 없이 재실행"
  exit 0
fi

echo ""
echo "▶ ArgoCD Application 적용 중"
KUBECONFIG="$KUBECONFIG" kubectl apply -f "$APP_YAML"

echo ""
echo "✓ ArgoCD Application 업데이트 완료 ($ENV)"
echo "  ArgoCD가 변경된 valuesObject로 자동 재배포합니다."
echo ""

if [[ -n "$WAIT" ]]; then
  echo "▶ 동기화 완료 대기 중..."
  KUBECONFIG="$KUBECONFIG" kubectl wait --for=jsonpath='{.status.health.status}'=Healthy \
    application/afterglow-"$ENV" -n argocd --timeout=10m 2>/dev/null || \
  KUBECONFIG="$KUBECONFIG" kubectl get application afterglow-"$ENV" -n argocd \
    -o jsonpath='{.status.sync.status} / {.status.health.status}' && echo ""
fi

echo "상태 확인:"
echo "  KUBECONFIG=$KUBECONFIG kubectl get pods -n afterglow-${ENV/#dev/dev}"
echo "  KUBECONFIG=$KUBECONFIG kubectl get application afterglow-$ENV -n argocd"
