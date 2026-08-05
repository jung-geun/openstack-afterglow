#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# afterglow × kolla-ansible integration installer
# Usage: ./deploy/kolla/install.sh [--apply-passwords]
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd ../.. && pwd)"
APPLY_PASSWORDS=false

for arg in "$@"; do
  case "$arg" in
    --apply-passwords) APPLY_PASSWORDS=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

log()  { echo "[afterglow-install] $*"; }
warn() { echo "[afterglow-install] WARNING: $*" >&2; }
die()  { echo "[afterglow-install] ERROR: $*" >&2; exit 1; }

# ── 1. kolla-ansible 설치 경로 탐지 ──────────────────────────────────────────
detect_kolla_dir() {
  # 우선순위 1: 환경변수
  if [[ -n "${KOLLA_ANSIBLE_DIR:-}" ]]; then
    echo "$KOLLA_ANSIBLE_DIR"
    return 0
  fi

  # 우선순위 2: python import 경로
  local py_path
  py_path=$(python3 -c "
import importlib.util, os, sys
spec = importlib.util.find_spec('kolla_ansible')
if spec is None:
    # kolla-ansible 패키지명이 다를 수 있으므로 share 경로 시도
    sys.exit(1)
# site-packages 내 kolla_ansible 디렉토리에서 share 경로 추론
pkg_dir = os.path.dirname(spec.origin)
# 패키지 루트에서 share 경로 찾기
for candidate in [
    os.path.join(sys.prefix, 'share', 'kolla-ansible'),
    '/usr/local/share/kolla-ansible',
    '/usr/share/kolla-ansible',
]:
    if os.path.isdir(candidate):
        print(candidate)
        sys.exit(0)
sys.exit(1)
" 2>/dev/null) && echo "$py_path" && return 0

  # 우선순위 3: 표준 경로
  for candidate in /usr/local/share/kolla-ansible /usr/share/kolla-ansible; do
    if [[ -d "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

log "kolla-ansible 설치 경로 탐지 중..."
KOLLA_DIR=$(detect_kolla_dir) || die "kolla-ansible 설치 경로를 찾을 수 없습니다. KOLLA_ANSIBLE_DIR 환경변수를 설정하거나 kolla-ansible을 먼저 설치하세요."
log "kolla-ansible 경로: $KOLLA_DIR"

# ── 2. 버전 검증 ──────────────────────────────────────────────────────────────
log "kolla-ansible 버전 검증 중..."
KOLLA_VERSION=$(kolla-ansible --version 2>&1 | grep -oP '\d+\.\d+' | head -1) || die "kolla-ansible 버전을 확인할 수 없습니다."
log "검출된 버전: $KOLLA_VERSION"

# 2025.2 이상 요구 (year * 100 + minor 형식으로 비교)
required_major=2025
required_minor=2

version_major=$(echo "$KOLLA_VERSION" | cut -d. -f1)
version_minor=$(echo "$KOLLA_VERSION" | cut -d. -f2)

if [[ "$version_major" -lt "$required_major" ]] || \
   { [[ "$version_major" -eq "$required_major" ]] && [[ "$version_minor" -lt "$required_minor" ]]; }; then
  die "kolla-ansible 버전이 2025.2 미만입니다 (현재: $KOLLA_VERSION). 최신 버전으로 업그레이드하세요."
fi
log "버전 검증 통과: $KOLLA_VERSION >= 2025.2"

# ── 3. role symlink 생성 ──────────────────────────────────────────────────────
ROLES_DIR="$KOLLA_DIR/ansible/roles"
if [[ ! -d "$ROLES_DIR" ]]; then
  die "kolla-ansible roles 디렉토리를 찾을 수 없습니다: $ROLES_DIR"
fi

ROLE_SRC="$REPO_DIR/deploy/kolla/ansible/roles/afterglow"
ROLE_LINK="$ROLES_DIR/afterglow"

log "afterglow role symlink 생성 중..."
if [[ -L "$ROLE_LINK" ]] && [[ "$(readlink "$ROLE_LINK")" == "$ROLE_SRC" ]]; then
  log "role symlink 이미 존재 (skip): $ROLE_LINK"
else
  ln -sfn "$ROLE_SRC" "$ROLE_LINK"
  log "role symlink 생성 완료: $ROLE_LINK -> $ROLE_SRC"
fi

WAYGATE_ROLE_SRC="$REPO_DIR/deploy/kolla/ansible/roles/waygate"
WAYGATE_ROLE_LINK="$ROLES_DIR/waygate"

log "waygate role symlink 생성 중..."
if [[ -L "$WAYGATE_ROLE_LINK" ]] && [[ "$(readlink "$WAYGATE_ROLE_LINK")" == "$WAYGATE_ROLE_SRC" ]]; then
  log "role symlink 이미 존재 (skip): $WAYGATE_ROLE_LINK"
else
  ln -sfn "$WAYGATE_ROLE_SRC" "$WAYGATE_ROLE_LINK"
  log "role symlink 생성 완료: $WAYGATE_ROLE_LINK -> $WAYGATE_ROLE_SRC"
fi
DROVER_ROLE_SRC="$REPO_DIR/deploy/kolla/ansible/roles/drover"
DROVER_ROLE_LINK="$ROLES_DIR/drover"

log "drover role symlink 생성 중..."
if [[ -L "$DROVER_ROLE_LINK" ]] && [[ "$(readlink "$DROVER_ROLE_LINK")" == "$DROVER_ROLE_SRC" ]]; then
  log "role symlink 이미 존재 (skip): $DROVER_ROLE_LINK"
else
  ln -sfn "$DROVER_ROLE_SRC" "$DROVER_ROLE_LINK"
  log "role symlink 생성 완료: $DROVER_ROLE_LINK -> $DROVER_ROLE_SRC"
fi
LUMEN_ROLE_SRC="$REPO_DIR/deploy/kolla/ansible/roles/lumen"
LUMEN_ROLE_LINK="$ROLES_DIR/lumen"

log "lumen role symlink 생성 중..."
if [[ -L "$LUMEN_ROLE_LINK" ]] && [[ "$(readlink "$LUMEN_ROLE_LINK")" == "$LUMEN_ROLE_SRC" ]]; then
  log "role symlink 이미 존재 (skip): $LUMEN_ROLE_LINK"
else
  ln -sfn "$LUMEN_ROLE_SRC" "$LUMEN_ROLE_LINK"
  log "role symlink 생성 완료: $LUMEN_ROLE_LINK -> $LUMEN_ROLE_SRC"
fi

# ── 4. play symlink 생성 ──────────────────────────────────────────────────────
PLAY_SRC="$REPO_DIR/deploy/kolla/playbooks/afterglow.yml"
PLAY_LINK="$KOLLA_DIR/ansible/afterglow.yml"

log "afterglow playbook symlink 생성 중..."
if [[ -L "$PLAY_LINK" ]] && [[ "$(readlink "$PLAY_LINK")" == "$PLAY_SRC" ]]; then
  log "play symlink 이미 존재 (skip): $PLAY_LINK"
else
  ln -sfn "$PLAY_SRC" "$PLAY_LINK"
  log "play symlink 생성 완료: $PLAY_LINK -> $PLAY_SRC"
fi

WAYGATE_PLAY_SRC="$REPO_DIR/deploy/kolla/playbooks/waygate.yml"
WAYGATE_PLAY_LINK="$KOLLA_DIR/ansible/waygate.yml"

log "waygate playbook symlink 생성 중..."
if [[ -L "$WAYGATE_PLAY_LINK" ]] && [[ "$(readlink "$WAYGATE_PLAY_LINK")" == "$WAYGATE_PLAY_SRC" ]]; then
  log "play symlink 이미 존재 (skip): $WAYGATE_PLAY_LINK"
else
  ln -sfn "$WAYGATE_PLAY_SRC" "$WAYGATE_PLAY_LINK"
  log "play symlink 생성 완료: $WAYGATE_PLAY_LINK -> $WAYGATE_PLAY_SRC"
fi
DROVER_PLAY_SRC="$REPO_DIR/deploy/kolla/playbooks/drover.yml"
DROVER_PLAY_LINK="$KOLLA_DIR/ansible/drover.yml"

log "drover playbook symlink 생성 중..."
if [[ -L "$DROVER_PLAY_LINK" ]] && [[ "$(readlink "$DROVER_PLAY_LINK")" == "$DROVER_PLAY_SRC" ]]; then
  log "play symlink 이미 존재 (skip): $DROVER_PLAY_LINK"
else
  ln -sfn "$DROVER_PLAY_SRC" "$DROVER_PLAY_LINK"
  log "play symlink 생성 완료: $DROVER_PLAY_LINK -> $DROVER_PLAY_SRC"
fi
LUMEN_PLAY_SRC="$REPO_DIR/deploy/kolla/playbooks/lumen.yml"
LUMEN_PLAY_LINK="$KOLLA_DIR/ansible/lumen.yml"

log "lumen playbook symlink 생성 중..."
if [[ -L "$LUMEN_PLAY_LINK" ]] && [[ "$(readlink "$LUMEN_PLAY_LINK")" == "$LUMEN_PLAY_SRC" ]]; then
  log "play symlink 이미 존재 (skip): $LUMEN_PLAY_LINK"
else
  ln -sfn "$LUMEN_PLAY_SRC" "$LUMEN_PLAY_LINK"
  log "play symlink 생성 완료: $LUMEN_PLAY_LINK -> $LUMEN_PLAY_SRC"
fi

# ── 5. site.yml 패치 ──────────────────────────────────────────────────────────
SITE_YML="$KOLLA_DIR/ansible/site.yml"
if [[ ! -f "$SITE_YML" ]]; then
  die "site.yml 파일을 찾을 수 없습니다: $SITE_YML"
fi

log "site.yml 패치 중: $SITE_YML"
python3 - "$SITE_YML" <<'PYEOF'
import sys, re

site_yml = sys.argv[1]
with open(site_yml) as f:
    content = f.read()

plays = []
if '# BEGIN afterglow integration' not in content:
    plays.append(
        '\n# BEGIN afterglow integration\n'
        '- name: Apply role afterglow\n'
        '  gather_facts: false\n'
        '  hosts:\n'
        '    - afterglow\n'
        "    - '&enable_afterglow_True'\n"
        "  serial: '{{ kolla_serial|default(\"0\") }}'\n"
        '  roles:\n'
        '    - { role: afterglow, tags: afterglow }\n'
        '# END afterglow integration\n'
    )

if '# BEGIN waygate integration' not in content:
    plays.append(
        '\n# BEGIN waygate integration\n'
        '- name: Apply role waygate\n'
        '  gather_facts: false\n'
        '  hosts:\n'
        '    - waygate\n'
        '    - haproxy\n'
        "    - '&enable_waygate_True'\n"
        "  serial: '{{ kolla_serial|default(\"0\") }}'\n"
        '  roles:\n'
        '    - { role: waygate, tags: waygate }\n'
        '# END waygate integration\n'
    )
if '# BEGIN drover integration' not in content:
    plays.append(
        '\n# BEGIN drover integration\n'
        '- name: Apply role drover\n'
        '  gather_facts: false\n'
        '  hosts:\n'
        '    - drover\n'
        '    - haproxy\n'
        "    - '&enable_drover_True'\n"
        "  serial: '{{ kolla_serial|default(\"0\") }}'\n"
        '  roles:\n'
        '    - { role: drover, tags: drover }\n'
        '# END drover integration\n'
    )
if '# BEGIN lumen integration' not in content:
    plays.append(
        '\n# BEGIN lumen integration\n'
        '- name: Apply role lumen\n'
        '  gather_facts: false\n'
        '  hosts:\n'
        '    - lumen\n'
        '    - haproxy\n'
        "    - '&enable_lumen_True'\n"
        "  serial: '{{ kolla_serial|default(\"0\") }}'\n"
        '  roles:\n'
        '    - { role: lumen, tags: lumen }\n'
        '# END lumen integration\n'
    )

if not plays:
    print('[afterglow-install] site.yml integrations already patched, skipping')
    sys.exit(0)

integration_plays = ''.join(plays)
lines = content.split('\n')

# Insert custom plays after Horizon when possible.
horizon_play_idx = None
for i, line in enumerate(lines):
    if re.match(r'^- name:\s+Apply role horizon\b', line):
        horizon_play_idx = i
        break

if horizon_play_idx is not None:
    insert_idx = len(lines)
    for i in range(horizon_play_idx + 1, len(lines)):
        if re.match(r'^- (name|hosts):', lines[i]):
            insert_idx = i
            break
    patch_lines = integration_plays.split('\n')
    new_lines = lines[:insert_idx] + patch_lines + lines[insert_idx:]
    open(site_yml, 'w').write('\n'.join(new_lines))
    print('[afterglow-install] site.yml integration patch complete')
else:
    print('[afterglow-install] WARNING: "Apply role horizon" play not found; appending integrations.')
    open(site_yml, 'w').write(content.rstrip('\n') + '\n' + integration_plays)
    print('[afterglow-install] site.yml integration patch complete at end of file')
PYEOF

# ── 6. passwords.yml merge (--apply-passwords 옵션) ───────────────────────────
if [[ "$APPLY_PASSWORDS" == true ]]; then
  PASSWORDS_YML="${KOLLA_PASSWORDS_FILE:-/etc/kolla/passwords.yml}"
  ADDITIONS_YML="$REPO_DIR/deploy/kolla/passwords.afterglow.additions.yml"

  if [[ ! -f "$PASSWORDS_YML" ]]; then
    die "passwords.yml 파일을 찾을 수 없습니다: $PASSWORDS_YML. KOLLA_PASSWORDS_FILE 환경변수로 경로를 지정하세요."
  fi

  log "passwords.yml merge 중: $PASSWORDS_YML"
  python3 - "$PASSWORDS_YML" "$ADDITIONS_YML" <<'PYEOF'
import sys
try:
    import yaml
except ImportError:
    print('[afterglow-install] ERROR: PyYAML이 설치되지 않았습니다. pip install pyyaml')
    sys.exit(1)

passwords_file = sys.argv[1]
additions_file = sys.argv[2]

with open(passwords_file) as f:
    passwords = yaml.safe_load(f) or {}

with open(additions_file) as f:
    additions = yaml.safe_load(f) or {}

added_keys = []
for key, value in additions.items():
    if key not in passwords:
        passwords[key] = value
        added_keys.append(key)
    else:
        print(f'[afterglow-install] 키 이미 존재, skip: {key}')

if added_keys:
    with open(passwords_file, 'w') as f:
        yaml.dump(passwords, f, default_flow_style=False, allow_unicode=True)
    print(f'[afterglow-install] passwords.yml에 추가된 키: {", ".join(added_keys)}')
else:
    print('[afterglow-install] passwords.yml: 추가할 새 키 없음')
PYEOF
fi

# ── 7. globals.yml enable_afterglow 확인 ──────────────────────────────────────
GLOBALS_YML="${KOLLA_GLOBALS_FILE:-/etc/kolla/globals.yml}"
if [[ -f "$GLOBALS_YML" ]]; then
  if ! grep -q "enable_afterglow" "$GLOBALS_YML"; then
    warn "globals.yml에 enable_afterglow 설정이 없습니다."
    warn "아래 내용을 $GLOBALS_YML 에 추가하세요:"
    warn "  enable_afterglow: \"yes\""
    warn "또는 $REPO_DIR/deploy/kolla/globals.afterglow.sample.yml 을 참조하세요."
  else
    log "globals.yml에 enable_afterglow 설정 확인됨"
  fi

  if ! grep -q "enable_waygate" "$GLOBALS_YML"; then
    warn "globals.yml에 enable_waygate 설정이 없습니다."
    warn "Waygate 배포 시 enable_waygate: \"yes\"를 추가하세요."
  else
    log "globals.yml에 enable_waygate 설정 확인됨"
  fi
  if ! grep -q "enable_drover" "$GLOBALS_YML"; then
    warn "globals.yml에 enable_drover 설정이 없습니다."
    warn "Drover 배포 시 enable_drover: \"yes\"를 추가하세요."
  else
    log "globals.yml에 enable_drover 설정 확인됨"
  fi
else
  warn "globals.yml 파일을 찾을 수 없습니다: $GLOBALS_YML"
  warn "KOLLA_GLOBALS_FILE 환경변수로 경로를 지정하거나, 수동으로 설정하세요."
fi

# ── 8. syntax-check ───────────────────────────────────────────────────────────
log "Ansible syntax-check 실행 중..."
if command -v ansible-playbook &>/dev/null; then
  ansible-playbook --syntax-check "$KOLLA_DIR/ansible/site.yml" && log "syntax-check 통과"
else
  warn "ansible-playbook 명령을 찾을 수 없습니다. syntax-check를 건너뜁니다."
fi

# ── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Afterglow, Waygate, and Drover integrations installed."
echo " Set enable_afterglow, enable_waygate, and enable_drover in globals.yml, then run:"
echo " kolla-ansible deploy -i <inventory>"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
