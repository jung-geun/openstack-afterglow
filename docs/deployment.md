# 배포 가이드

**Language:** 한국어 · [English](en/deployment.md)

Afterglow는 Docker Compose(개발/소규모), Kubernetes(프로덕션), ArgoCD(GitOps) 세 가지 배포 방식을 지원합니다.

---

## 사전 요구사항

### OpenStack 서비스

| 서비스 | 필수 여부 | 용도 |
|---|---|---|
| Keystone | 필수 | 인증 |
| Nova | 필수 | VM 컴퓨트 |
| Glance | 필수 | 이미지 관리 |
| Cinder | 필수 | 블록 스토리지 |
| Neutron | 필수 | 네트워크 |
| Manila | 선택 | 공유 파일시스템 (OverlayFS 기능) |
| Octavia | 선택 | 로드밸런서 |

---

## Docker Compose 배포

개발 환경 또는 단일 호스트 소규모 배포에 적합합니다.

### 1. 저장소 클론 및 설정

```bash
git clone git@github.com:jung-geun/openstack-afterglow.git
cd openstack-afterglow
cp config.toml.example config.toml
```

`config.toml` 필수 항목 설정:

```toml
[openstack]
auth_url             = "https://keystone.example.com:5000/v3"
project_name         = "myproject"
project_domain_name  = "Default"
user_domain_name     = "Default"
region_name          = "RegionOne"

[app]
secret_key = "your-random-secret-key-change-me"  # 반드시 변경

[nova]
default_network_id = "your-network-uuid"
```

### 1-b. 설정 오버라이드 (선택)

긴 옵션 섹션(GPU 디바이스 맵 등)은 별도 오버라이드 파일로 분리할 수 있습니다.  
`config.toml`과 같은 디렉토리에 `config.<name>.toml`을 두면 백엔드 기동 시 알파벳순으로 딥 머지됩니다.

**머지 규칙**: `dict`는 재귀 병합, `list`와 스칼라는 오버라이드 파일이 덮어씁니다.

```bash
# GPU 디바이스 맵 활성화 예시
cp config.gpu.toml.example config.gpu.toml
# config.gpu.toml 을 편집하여 실제 환경의 GPU PCI ID 반영
```

여러 오버라이드 파일을 동시에 사용할 수 있습니다:

```
config.toml          ← 베이스 설정
config.gpu.toml      ← GPU 디바이스 맵 오버라이드
config.openstack.toml  ← OpenStack 자격증명 오버라이드 (선택)
```

파일명 예시 처럼 알파벳순(`g` < `o`)으로 적용되며 뒤 파일이 앞 파일을 이깁니다.

### 2. 서비스 시작

```bash
# 기본 서비스 (backend + frontend + redis)
docker compose up -d

# 모니터링 스택 포함
docker compose --profile monitoring up -d
```

### 3. 접속 확인

```bash
# 헬스체크
curl http://localhost:8000/api/health

# 브라우저
open http://localhost:3000
```

### 서비스 구성

| 서비스 | 포트 | 설명 |
|---|---|---|
| frontend | 3000 | SvelteKit 웹 UI |
| backend | 8000 | FastAPI REST API |
| redis | 6379 | 캐시 / 세션 (AOF 영속화) |
| opensearch | 9200 | 로그 검색 (모니터링) |
| prometheus | 9090 | 메트릭 수집 (모니터링) |
| grafana | 3001 | 대시보드 (모니터링) |

---

## kolla-ansible 배포

OpenStack 환경 내부(컨트롤러 노드)에서 kolla-ansible 플레이북으로 Afterglow를 배포합니다. Docker 기반 서비스를 기존 kolla 인프라와 동일한 방식으로 관리합니다.

### 사전 요구사항

- kolla-ansible 환경 구성 완료 (`/etc/kolla/globals.yml`, `/etc/kolla/passwords.yml` 존재)
- Afterglow 컨테이너 이미지 접근 가능 (GHCR 또는 내부 레지스트리)
- Python 가상 환경에 kolla-ansible 설치

### 1. 역할 설치

```bash
# 저장소 클론
git clone git@github.com:jung-geun/openstack-afterglow.git
cd openstack-afterglow/deploy/kolla

# kolla-ansible 가상 환경 활성화
source /path/to/kolla-venv/bin/activate

# Afterglow 역할이 kolla-ansible 역할 경로에 있어야 함
# (install.sh가 자동으로 복사)
bash install.sh
```

### 2. globals.yml 설정

`/etc/kolla/globals.yml`에 Afterglow 관련 변수 추가:

```yaml
# Afterglow 활성화
enable_afterglow: "yes"
enable_afterglow_frontend: "yes"
enable_afterglow_worker: "yes"

# 접근 URL (외부에서 접근 가능한 주소)
afterglow_external_url: "https://afterglow.example.com"

# 이미지 설정
afterglow_backend_image: "ghcr.io/jung-geun/afterglow-api"
afterglow_frontend_image: "ghcr.io/jung-geun/afterglow"
afterglow_image_tag: "latest"

# OpenStack 서비스 연결
afterglow_service_project_name: "service"
afterglow_admin_keystone_user: "afterglow"
```

### 3. 패스워드 설정

`/etc/kolla/passwords.yml`에 추가:

```yaml
afterglow_admin_keystone_password: "<keystone-password>"
afterglow_database_password: "<db-password>"
afterglow_secret_key: "<random-32-char-key>"
afterglow_redis_password: ""  # Redis 인증 미사용 시 빈 문자열
```

### 4. 배포 실행

```bash
# 배포
kolla-ansible deploy -i /etc/kolla/inventory --tags afterglow

# 설정만 반영 (재시작 없이)
kolla-ansible reconfigure -i /etc/kolla/inventory --tags afterglow
```

### 5. 서비스 확인

```bash
# Docker 컨테이너 상태 확인
docker ps | grep afterglow

# 로그 확인
docker logs afterglow_backend
docker logs afterglow_frontend
docker logs afterglow_worker
```

---

## Kubernetes 배포

프로덕션 환경 배포. Kustomize 기반 base + overlay 구조로 dev/prod 환경을 분리합니다.

### 사전 요구사항

| 항목 | 최소 버전 |
|---|---|
| kubectl | 1.28+ |
| k3s 또는 Kubernetes | 1.28+ |
| (선택) ArgoCD | 2.8+ |

### 디렉토리 구조

```
deploy/k8s-template/
├── base/              # 공통 리소스
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── ingress.yaml
│   ├── cert-manager.yaml
│   ├── backend/
│   ├── frontend/
│   ├── redis/
│   ├── worker/
│   └── monitoring/
└── overlays/
    ├── dev/           # 개발 오버레이
    └── prod/          # 프로덕션 오버레이
```

### 1. 네임스페이스 및 시크릿 생성

```bash
kubectl create namespace afterglow

kubectl create secret generic afterglow-secrets \
  --namespace=afterglow \
  --from-literal=OPENSTACK_PASSWORD=<password> \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)
```

### 2. Kustomize 배포

```bash
# 개발 환경
kubectl apply -k deploy/k8s-template/overlays/dev

# 프로덕션 환경
kubectl apply -k deploy/k8s-template/overlays/prod
```

### 3. 배포 확인

```bash
kubectl get all -n afterglow
kubectl get ingress -n afterglow

# 로그 확인
kubectl logs -f deployment/backend -n afterglow
kubectl logs -f deployment/frontend -n afterglow
```

### ConfigMap 주요 설정

`deploy/k8s-template/base/configmap.yaml` 수정:

```yaml
data:
  OPENSTACK_AUTH_URL: "https://keystone.example.com:5000/v3"
  OPENSTACK_PROJECT_NAME: "myproject"
  OPENSTACK_REGION_NAME: "RegionOne"
  REDIS_URL: "redis://redis:6379/0"
```

### Ingress 도메인 설정

`deploy/k8s-template/base/ingress.yaml`:

```yaml
spec:
  rules:
    - host: afterglow.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 3000
```

> **주의**: 프론트엔드 `PUBLIC_API_BASE` 환경변수는 브라우저에서 직접 접근 가능한 외부 URL로 설정해야 합니다. 클러스터 내부 주소(`http://backend:8000`)로 설정하면 브라우저에서 접근할 수 없습니다.

```yaml
# frontend Deployment 환경변수
- name: PUBLIC_API_BASE
  value: "https://afterglow.example.com"
- name: ORIGIN
  value: "https://afterglow.example.com"
```

### 모니터링 스택

```bash
# 전체 모니터링 배포
kubectl apply -f deploy/k8s-template/base/monitoring/

# 포트 포워딩으로 로컬 접근
kubectl port-forward svc/grafana 3001:3000 -n afterglow
kubectl port-forward svc/prometheus 9090:9090 -n afterglow
```

---

## ArgoCD GitOps 배포

`dev` 브랜치의 변경사항을 자동으로 클러스터에 동기화합니다.

### 1. ArgoCD 설치 (없는 경우)

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. Application 등록

```bash
kubectl apply -f argocd/appproject.yaml
kubectl apply -f argocd/application.dev.yaml    # 개발
kubectl apply -f argocd/application.prod.yaml   # 프로덕션
```

`argocd/application.dev.yaml` 주요 설정:

```yaml
spec:
  source:
    repoURL: https://github.com/jung-geun/openstack-afterglow
    targetRevision: dev          # 감시할 브랜치
    path: deploy/k8s-template/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: afterglow-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 3. 동기화 확인

```bash
argocd app list
argocd app sync afterglow-dev
argocd app get afterglow-dev
```

---

## TLS / HTTPS 설정

cert-manager를 사용하여 Let's Encrypt 인증서를 자동으로 발급합니다.

```bash
# cert-manager 설치
kubectl apply -f deploy/k8s-template/base/cert-manager.yaml
```

ClusterIssuer 생성:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

Ingress에 TLS 추가:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - afterglow.example.com
      secretName: afterglow-tls
```

---

## 업그레이드

### Docker Compose

```bash
git pull origin dev
docker compose pull
docker compose up -d
```

### Kubernetes

```bash
# 이미지 업데이트 후 롤링 재시작
kubectl rollout restart deployment/backend -n afterglow
kubectl rollout restart deployment/frontend -n afterglow
kubectl rollout status deployment/backend -n afterglow
```

ArgoCD를 사용하는 경우 `dev` 브랜치 푸시 시 자동 동기화됩니다.

---

## 문제 해결

### 백엔드가 OpenStack에 연결되지 않음

```bash
# 로그 확인
docker compose logs backend
kubectl logs -f deployment/backend -n afterglow

# Keystone 연결 테스트
curl -s https://keystone.example.com:5000/v3 | python3 -m json.tool
```

### Redis 연결 오류

```bash
docker compose exec backend redis-cli -u redis://redis:6379 ping
# 또는
kubectl exec -n afterglow deployment/backend -- redis-cli -u redis://redis:6379 ping
```

### 프론트엔드 API 연결 오류

1. `PUBLIC_API_BASE`가 브라우저에서 접근 가능한 외부 URL인지 확인
2. 도메인 변경 후 프론트엔드 재시작:
   ```bash
   kubectl rollout restart deployment/frontend -n afterglow
   ```

### Pod가 Pending 상태

```bash
kubectl describe pod -l app=backend -n afterglow
# PVC 바인딩 또는 리소스 부족 여부 확인
kubectl get pvc -n afterglow
kubectl describe nodes
```

---

## 보안 체크리스트 (배포 전)

자세한 보안 모델은 [docs/security.md](security.md) 참고.

### 필수 환경 변수

| 변수 | 운영 시 |
|---|---|
| `AFTERGLOW_ENV=production` | 필수 |
| `AFTERGLOW_ALLOW_INSECURE` | **설정 금지** (production 과 결합 시 백엔드가 ValueError 로 부팅 실패) |
| `SECRET_KEY` | 32 자 이상 random hex (`change-me-in-production` default 금지) |
| `K3S_KUBECONFIG_ENCRYPTION_KEY` | 64 hex chars (`openssl rand -hex 32`) — kubeconfig/node_token/manager_password/notion 의 마스터키. HKDF 로 도메인별 sub-key 자동 파생 |
| `NOTION_CONFIG_ENCRYPTION_KEY` | 선택. 미설정 시 K3S_KUBECONFIG_ENCRYPTION_KEY 와 동일 마스터로 fallback (HKDF 로 분리됨) |
| `TRUSTED_PROXIES` | 리버스 프록시의 CIDR 리스트. 기본 `127.0.0.1/32, ::1/128` — 실제 LB IP 추가 필요 |
| `CORS_ORIGIN_LIST` | 신뢰할 수 있는 origin 만. wildcard 금지 |

### 부팅 가드 검증

```bash
# 의도적으로 잘못된 조합으로 부팅 시도 → ValueError 가 떠야 함
AFTERGLOW_ENV=production AFTERGLOW_ALLOW_INSECURE=1 \
  uv run uvicorn app.main:app --port 8000
# 예상: "AFTERGLOW_ALLOW_INSECURE=1 must NOT be set when AFTERGLOW_ENV=production"
```

### 정기 점검

- **audit_log retention** — `kubeconfig_download` row 가 적정 기간 (예: 90일) 보관되는지
- **Health Bearer 토큰** — `redis-cli SCAN MATCH afterglow:health:token:*` 의 TTL 이 7일 이내인지
- **K3s ciphertext 버전** — `encrypted_kubeconfig NOT LIKE 'v3:%'` 행의 갯수 (1.15.0 전에 모두 v3 로 마이그레이션 권장)

### 1.13.x → 1.14.0 업그레이드

- **Backward-compatible**, 마이그레이션 작업 불필요
- 다른 프로젝트의 ID 로 자원에 접근하던 자동화 스크립트는 404 를 받게 됨 — admin 토큰 또는 application credential 로 전환 필요
- 첫 v2/legacy ciphertext 복호화 시 워커당 1회 deprecation warning 로그 확인 (스팸 X)

### 1.14.0 → 1.15.0 (예정) 전 필수 작업

- 별도 PR 로 제공될 마이그레이션 스크립트로 모든 v1/v2 ciphertext 를 v3 로 batch re-encrypt
- 미실행 시 v1/v2 ciphertext 가 영구 복호화 불가
