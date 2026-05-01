#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# afterglow × kolla-ansible integration uninstaller
# Usage: ./deploy/kolla/uninstall.sh
# ─────────────────────────────────────────────────────────────────────────────

log()  { echo "[afterglow-uninstall] $*"; }
warn() { echo "[afterglow-uninstall] WARNING: $*" >&2; }
die()  { echo "[afterglow-uninstall] ERROR: $*" >&2; exit 1; }

# ── kolla-ansible 설치 경로 탐지 ──────────────────────────────────────────────
detect_kolla_dir() {
  if [[ -n "${KOLLA_ANSIBLE_DIR:-}" ]]; then
    echo "$KOLLA_ANSIBLE_DIR"
    return 0
  fi

  local py_path
  py_path=$(python3 -c "
import sys, os
for candidate in [
    '/usr/local/share/kolla-ansible',
    '/usr/share/kolla-ansible',
]:
    if os.path.isdir(candidate):
        print(candidate)
        sys.exit(0)
sys.exit(1)
" 2>/dev/null) && echo "$py_path" && return 0

  for candidate in /usr/local/share/kolla-ansible /usr/share/kolla-ansible; do
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

# ── 1. role symlink 제거 ──────────────────────────────────────────────────────
ROLE_LINK="$KOLLA_DIR/ansible/roles/afterglow"
if [[ -L "$ROLE_LINK" ]]; then
  rm -f "$ROLE_LINK"
  log "role symlink 제거 완료: $ROLE_LINK"
elif [[ -e "$ROLE_LINK" ]]; then
  warn "$ROLE_LINK 는 symlink가 아닙니다. 수동으로 확인하세요."
else
  log "role symlink 없음 (skip): $ROLE_LINK"
fi

# ── 2. play symlink 제거 ──────────────────────────────────────────────────────
PLAY_LINK="$KOLLA_DIR/ansible/afterglow.yml"
if [[ -L "$PLAY_LINK" ]]; then
  rm -f "$PLAY_LINK"
  log "play symlink 제거 완료: $PLAY_LINK"
elif [[ -e "$PLAY_LINK" ]]; then
  warn "$PLAY_LINK 는 symlink가 아닙니다. 수동으로 확인하세요."
else
  log "play symlink 없음 (skip): $PLAY_LINK"
fi

# ── 3. site.yml에서 marker 블록 제거 ─────────────────────────────────────────
SITE_YML="$KOLLA_DIR/ansible/site.yml"
if [[ ! -f "$SITE_YML" ]]; then
  warn "site.yml 파일을 찾을 수 없습니다: $SITE_YML"
else
  log "site.yml에서 afterglow integration 블록 제거 중..."
  python3 - "$SITE_YML" <<'PYEOF'
import sys, re

site_yml = sys.argv[1]
content = open(site_yml).read()

if '# BEGIN afterglow integration' not in content:
    print('[afterglow-uninstall] site.yml에 afterglow 블록 없음 (skip)')
    sys.exit(0)

# BEGIN ~ END 마커 블록(포함) 제거, 앞의 빈 줄도 함께 정리
new_content = re.sub(
    r'\n?# BEGIN afterglow integration\n.*?# END afterglow integration\n',
    '',
    content,
    flags=re.DOTALL
)
open(site_yml, 'w').write(new_content)
print('[afterglow-uninstall] site.yml에서 afterglow integration 블록 제거 완료')
PYEOF
fi

# ── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " afterglow integration uninstalled."
echo " globals.yml 및 passwords.yml은 변경되지 않았습니다."
echo " 필요하면 수동으로 afterglow 관련 설정을 제거하세요."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
