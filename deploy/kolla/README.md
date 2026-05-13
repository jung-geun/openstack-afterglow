# afterglow × kolla-ansible 통합 가이드

afterglow를 기존 kolla-ansible 배포에 통합하여 `kolla-ansible deploy` 한 줄로 함께 배포합니다.

---

## 개요

`install.sh`는 사용자의 kolla-ansible 설치에 멱등하게 패치를 적용합니다:

- afterglow Ansible role symlink를 kolla-ansible roles 디렉토리에 연결
- afterglow playbook symlink를 kolla-ansible ansible 디렉토리에 연결
- `site.yml`에 `import_playbook: afterglow.yml` 라인을 삽입

이후에는 표준 `kolla-ansible deploy` 명령만 사용하면 afterglow도 함께 배포됩니다.

---

## 사전 요구 사항

| 항목 | 요구 버전 / 조건 |
|------|-----------------|
| kolla-ansible | 2025.2 이상 |
| OpenStack 서비스 | MariaDB, Valkey(Redis), Keystone, Manila, HAProxy 포함 |
| Python | 3.10 이상 (PyYAML 포함) |
| Ansible | kolla-ansible과 함께 설치된 버전 |
| GHCR 접근 | private 이미지 사용 시 Personal Access Token 필요 |

---

## 설치 (3단계)

### 1단계: install.sh 실행

```bash
# afterglow 저장소 루트에서 실행
./deploy/kolla/install.sh

# passwords.yml에 afterglow 항목을 자동으로 추가하려면
./deploy/kolla/install.sh --apply-passwords

# kolla-ansible 경로를 직접 지정하려면
KOLLA_ANSIBLE_DIR=/path/to/kolla-ansible ./deploy/kolla/install.sh
```

스크립트는 다음 작업을 수행합니다:
- kolla-ansible 설치 경로 자동 탐지
- 버전 검증 (2025.2 이상 요구)
- role 및 playbook symlink 생성 (멱등)
- `site.yml` 패치 (이미 패치된 경우 skip)
- Ansible syntax-check 실행

### 2단계: 설정 파일 준비

**globals.yml 설정:**

```bash
# 샘플 파일을 참조하여 /etc/kolla/globals.yml에 추가
cat deploy/kolla/globals.afterglow.sample.yml >> /etc/kolla/globals.yml

# 최소 필수 설정:
# enable_afterglow: "yes"
# afterglow_image_tag: "latest"
# afterglow_ceph_monitors: "10.0.0.1:6789,..."  (Manila CephFS 사용 시)
```

**passwords.yml 설정:**

```bash
# 샘플 파일을 참조하여 /etc/kolla/passwords.yml에 추가 후 값 채우기
cat deploy/kolla/passwords.afterglow.additions.yml >> /etc/kolla/passwords.yml

# 또는 install.sh --apply-passwords 로 자동 merge

# 각 패스워드 항목 생성:
# afterglow_database_password: $(python3 -c "import secrets; print(secrets.token_hex(16))")
# afterglow_secret_key: $(python3 -c "import secrets; print(secrets.token_hex(32))")
# afterglow_kubeconfig_encryption_key: $(openssl rand -hex 32)
```

### 3단계: 배포

```bash
# multinode 배포 (평소와 동일)
kolla-ansible deploy -i deploy/kolla/inventory/multinode.sample

# all-in-one 배포
kolla-ansible deploy -i deploy/kolla/inventory/all-in-one.sample

# bootstrap 및 사전 점검 포함 전체 배포
kolla-ansible bootstrap-servers -i <inventory>
kolla-ansible prechecks -i <inventory>
kolla-ansible deploy -i <inventory>
```

---

## 제거

```bash
./deploy/kolla/uninstall.sh
```

- role symlink, play symlink 제거
- `site.yml`에서 afterglow 블록 제거
- `globals.yml` 및 `passwords.yml`은 변경하지 않음 (수동 정리 필요)

---

## afterglow만 단독 재배포

```bash
# afterglow 태그만 실행
kolla-ansible deploy -i <inventory> --tags afterglow

# 컨테이너 삭제
ansible-playbook -i <inventory> deploy/kolla/playbooks/destroy.yml
```

---

## 설정 변수 설명

### globals.yml 주요 항목

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `enable_afterglow` | `"no"` | afterglow 전체 활성화 마스터 토글 |
| `enable_afterglow_backend` | `"yes"` | FastAPI 백엔드 컨테이너 |
| `enable_afterglow_frontend` | `"yes"` | SvelteKit 프론트엔드 컨테이너 |
| `enable_afterglow_worker` | `"yes"` | 비동기 워커 컨테이너 |
| `afterglow_image_namespace` | `"ghcr.io/openstack-afterglow"` | 컨테이너 이미지 레지스트리 네임스페이스 |
| `afterglow_image_tag` | `"latest"` | 컨테이너 이미지 태그 |
| `afterglow_image_pull_secret_b64` | `""` | GHCR private 이미지 접근용 Docker config base64 |
| `afterglow_external_url` | `"https://{{ kolla_external_fqdn }}"` | afterglow 외부 접근 URL |
| `afterglow_database_name` | `"afterglow"` | MariaDB 데이터베이스 이름 |
| `afterglow_redis_db_index` | `5` | Redis DB 인덱스 (타 서비스 충돌 방지) |
| `afterglow_manila_microversion` | `"2.65"` | Manila API microversion |
| `afterglow_manila_share_type` | `"cephfs"` | Manila share type |
| `afterglow_ceph_monitors` | `""` | CephFS 모니터 주소 (콤마 구분) |
| `afterglow_cephx_user` | `"client.afterglow"` | Manila CephX 접근 ID |
| `afterglow_service_manila_enabled` | `true` | Manila 연동 활성화 |
| `afterglow_service_k3s_enabled` | `true` | k3s 프로비저닝 기능 활성화 |

### passwords.yml 주요 항목

| 변수 | 생성 방법 | 설명 |
|------|-----------|------|
| `afterglow_database_password` | `python3 -c "import secrets; print(secrets.token_hex(16))"` | MariaDB afterglow 사용자 비밀번호 |
| `afterglow_secret_key` | `python3 -c "import secrets; print(secrets.token_hex(32))"` | FastAPI JWT/세션 서명 키 (64 hex char) |
| `afterglow_kubeconfig_encryption_key` | `openssl rand -hex 32` | kubeconfig AES-256-GCM 암호화 키 |
| `afterglow_oidc_client_secret` | GitLab/OIDC 제공자에서 발급 | OIDC Client Secret |
| `afterglow_admin_keystone_password` | 임의 생성 | Keystone afterglow_admin 비밀번호 |

---

## 검증 명령어

```bash
# Ansible syntax-check
ansible-playbook --syntax-check /usr/local/share/kolla-ansible/ansible/site.yml

# afterglow role symlink 확인
ls -la /usr/local/share/kolla-ansible/ansible/roles/afterglow

# afterglow playbook symlink 확인
ls -la /usr/local/share/kolla-ansible/ansible/afterglow.yml

# site.yml 패치 확인
grep -A3 "afterglow integration" /usr/local/share/kolla-ansible/ansible/site.yml

# 배포 dry-run (check mode)
kolla-ansible deploy -i <inventory> --tags afterglow --check

# 컨테이너 상태 확인 (배포 후)
kolla-ansible status -i <inventory>
```

---

## 주의 사항

### GHCR private 이미지

afterglow 이미지가 GHCR private 저장소에 있는 경우, `afterglow_image_pull_secret_b64`를 반드시 설정해야 합니다:

```bash
# Docker config JSON 생성 및 base64 인코딩
echo '{"auths":{"ghcr.io":{"auth":"'"$(echo -n 'USER:TOKEN' | base64)"'"}}}' | base64
```

생성된 값을 `globals.yml`의 `afterglow_image_pull_secret_b64`에 설정하세요.

### Manila microversion

afterglow는 Manila API microversion 2.65 이상을 요구합니다. kolla-ansible의 Manila 버전이 이를 지원하는지 확인하세요. 일부 구버전 OpenStack에서는 microversion을 낮춰야 할 수 있습니다.

### CephFS 모니터 주소

`afterglow_ceph_monitors`는 cloud-init 마운트 및 컨테이너 내 CephFS 마운트에 사용됩니다. 형식은 `IP:PORT` 콤마 구분이며, Ceph Monitor 노드 IP를 정확히 입력해야 합니다:

```yaml
afterglow_ceph_monitors: "10.0.0.1:6789,10.0.0.2:6789,10.0.0.3:6789"
```

---

## 디렉토리 구조

```
deploy/kolla/
├── install.sh                        # kolla-ansible 통합 설치 스크립트
├── uninstall.sh                      # 통합 제거 스크립트
├── ansible.cfg                       # Ansible 설정
├── globals.afterglow.sample.yml      # globals.yml 추가 설정 샘플
├── passwords.afterglow.additions.yml # passwords.yml 추가 항목 샘플
├── ansible/
│   └── roles/
│       └── afterglow/                # afterglow Ansible role (symlink 대상)
├── inventory/
│   ├── multinode.sample              # 멀티노드 인벤토리 샘플
│   └── all-in-one.sample             # 단일노드 인벤토리 샘플
└── playbooks/
    ├── afterglow.yml                 # afterglow 배포 playbook (symlink 대상)
    └── destroy.yml                   # afterglow 컨테이너 삭제 playbook
```
