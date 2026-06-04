#!/usr/bin/env bash
# 로컬에서 GitHub Actions CI를 재현하는 스크립트.
# commit 전 반드시 실행: bash scripts/ci-local.sh
#
# 실행 단계:
#   1. version-check  — 버전 동기화 검증
#   2. backend lint   — ruff check + format check
#   3. backend test   — pytest (integration 제외)
#   4. frontend test  — bun install (frozen) + vitest
#
# 옵션:
#   --fix   ruff 자동 수정 후 검사 (lint 에러 있을 때 사용)
#   --skip-frontend   프론트엔드 테스트 생략

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
FRONTEND="$REPO_ROOT/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

FIX_MODE=false
SKIP_FRONTEND=false
for arg in "$@"; do
  case $arg in
    --fix) FIX_MODE=true ;;
    --skip-frontend) SKIP_FRONTEND=true ;;
  esac
done

pass() { echo -e "${GREEN}✓${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }
step() { echo -e "\n${CYAN}${BOLD}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }

FAILURES=()

run_step() {
  local name="$1"; shift
  if "$@"; then
    pass "$name"
  else
    fail "$name"
    FAILURES+=("$name")
  fi
}

# ── 1. Version check ────────────────────────────────────────────────────────
step "Version sync check"
run_step "version-sync" bash "$REPO_ROOT/scripts/check-version-sync.sh"

# ── 2. Backend lint ─────────────────────────────────────────────────────────
step "Backend lint (ruff)"
cd "$BACKEND"

if $FIX_MODE; then
  warn "--fix 모드: ruff 자동 수정 실행"
  uv run ruff check --fix . || true
  uv run ruff format . || true
fi

run_step "ruff check" uv run ruff check .
run_step "ruff format" uv run ruff format --check .

# ── 3. Backend unit tests ───────────────────────────────────────────────────
step "Backend unit tests (integration 제외)"
cd "$BACKEND"
run_step "pytest" env AFTERGLOW_ALLOW_INSECURE=1 \
  uv run python -m pytest tests/ --ignore=tests/integration -q

# ── 4. Frontend ─────────────────────────────────────────────────────────────
if $SKIP_FRONTEND; then
  warn "프론트엔드 테스트 생략 (--skip-frontend)"
else
  step "Frontend (bun install + vitest)"
  cd "$FRONTEND"
  run_step "bun install (frozen)" bun install --frozen-lockfile
  run_step "vitest" bun run test
fi

# ── 결과 요약 ────────────────────────────────────────────────────────────────
echo ""
if [ ${#FAILURES[@]} -eq 0 ]; then
  echo -e "${GREEN}${BOLD}✓ 모든 CI 검사 통과 — commit 가능${NC}"
  exit 0
else
  echo -e "${RED}${BOLD}✗ 실패한 단계:${NC}"
  for f in "${FAILURES[@]}"; do
    echo -e "  ${RED}•${NC} $f"
  done
  echo ""
  echo -e "${YELLOW}hint: lint 에러는 'bash scripts/ci-local.sh --fix' 로 자동 수정${NC}"
  exit 1
fi
