#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# afterglow × kolla-ansible integration uninstaller
# Usage: ./deploy/kolla/uninstall.sh
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR="${AFTERGLOW_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd ../.. && pwd)}"

log()  { echo "[afterglow-uninstall] $*"; }
warn() { echo "[afterglow-uninstall] WARNING: $*" >&2; }
die()  { echo "[afterglow-uninstall] ERROR: $*" >&2; exit 1; }

detect_kolla_dir() {
  if [[ -n "${KOLLA_ANSIBLE_DIR:-}" ]]; then
    echo "$KOLLA_ANSIBLE_DIR"
    return 0
  fi

  if [[ -n "${KOLLA_ANSIBLE_BIN:-}" ]]; then
    local bin_prefix
    bin_prefix=$(cd "$(dirname "$KOLLA_ANSIBLE_BIN")/.." && pwd)
    if [[ -d "$bin_prefix/share/kolla-ansible" ]]; then
      echo "$bin_prefix/share/kolla-ansible"
      return 0
    fi
    if [[ -d "$bin_prefix/local/share/kolla-ansible" ]]; then
      echo "$bin_prefix/local/share/kolla-ansible"
      return 0
    fi
  fi

  local py_path
  py_path=$(python3 -c "
import sys, os
for candidate in [
    '/etc/kolla/.venv/share/kolla-ansible',
    '/usr/local/share/kolla-ansible',
    '/usr/share/kolla-ansible',
]:
    if os.path.isdir(candidate):
        print(candidate)
        sys.exit(0)
sys.exit(1)
" 2>/dev/null) && echo "$py_path" && return 0

  for candidate in /etc/kolla/.venv/share/kolla-ansible /usr/local/share/kolla-ansible /usr/share/kolla-ansible; do
    if [[ -d "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

log "kolla-ansible 설치 경로 탐지 중..."
KOLLA_DIR=$(detect_kolla_dir) || die "kolla-ansible 설치 경로를 찾을 수 없습니다. KOLLA_ANSIBLE_DIR 환경변수를 설정하세요."
log "kolla-ansible 경로: $KOLLA_DIR"

remove_symlink_safe() {
  local target="$1"
  local link_path="$2"
  local desc="$3"

  log "$desc 심볼릭 링크 제거 확인 중: $link_path"

  if [[ ! -e "$link_path" && ! -L "$link_path" ]]; then
    log "$link_path 존재하지 않음 (skip)"
    return 0
  fi

  if [[ ! -L "$link_path" ]]; then
    die "제거 거부: $link_path 가 심볼릭 링크가 아닙니다."
  fi

  local current_target
  current_target=$(readlink "$link_path" || true)
  local current_real expected_real
  current_real=$(realpath "$link_path" 2>/dev/null || true)
  expected_real=$(realpath "$target" 2>/dev/null || true)

  if [[ "$current_target" != "$target" ]] && [[ -z "$expected_real" || "$current_real" != "$expected_real" ]]; then
    die "제거 거부: $link_path 가 예상 대상($target)을 가리키지 않습니다 (현재: $current_target)."
  fi

  rm "$link_path" || die "$link_path 심볼릭 링크 제거 실패"
  log "심볼릭 링크 제거 완료: $link_path"
}

ROLES_DIR="$KOLLA_DIR/ansible/roles"

# 1. 4개 Role 심볼릭 링크 제거
remove_symlink_safe "$REPO_DIR/deploy/kolla/ansible/roles/afterglow" "$ROLES_DIR/afterglow" "afterglow role"
remove_symlink_safe "$REPO_DIR/deploy/kolla/ansible/roles/waygate" "$ROLES_DIR/waygate" "waygate role"
remove_symlink_safe "$REPO_DIR/deploy/kolla/ansible/roles/drover" "$ROLES_DIR/drover" "drover role"
remove_symlink_safe "$REPO_DIR/deploy/kolla/ansible/roles/lumen" "$ROLES_DIR/lumen" "lumen role"

# 2. 1개 Aggregate playbook 심볼릭 링크 제거
remove_symlink_safe "$REPO_DIR/deploy/kolla/site.yml" "$KOLLA_DIR/ansible/afterglow-site.yml" "aggregate afterglow-site.yml playbook"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Afterglow integration symlinks removed."
echo " Stock site.yml, globals.yml, passwords.yml, databases, containers, images,"
echo " and source checkouts remain UNTOUCHED."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
