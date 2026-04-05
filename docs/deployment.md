# Union 배포 가이드

## 사전 요구사항

| 항목 | 최소 버전 | 확인 명령 |
|------|-----------|-----------|
| Docker | 24.0 이상 | `docker --version` |
| Docker Compose | 2.x 이상 | `docker compose version` |
| OpenStack 접근 권한 | Keystone v3 | — |
| (선택) kubectl | 1.28 이상 | `kubectl version` |

OpenStack 측 필요 서비스:

- Keystone (인증)
- Nova (컴퓨트)
- Glance (이미지)
- Cinder (블록 스토리지)
- Neutron (네트워크)
- Manila (공유 파일시스템, CephFS 백엔드)

---

## Docker Compose 배포

### 1단계: 저장소 클론

```bash
git clone https://github.com/your-org/union.git
cd union
```

### 2단계: 설정 파일 준비

```bash
cp union.toml.ecample union.toml
```

텍스트 편집기로 `union.toml`을 열고 OpenStack 자격증명과 환경에 맞는 값을 입력합니다. 필수 항목은 아래 "union.toml 설정 상세" 섹션을 참고하세요.

### 3단계: 서비스 시작

```bash
docker compose up -d
```

다음 서비스가 시작됩니다.

| 서비스 | 포트 | 설명 |
|--------|------|------|
| redis | 6379 | 캐시 및 세션 저장소 |
| backend | 8000 | FastAPI 백엔드 |
| frontend | 3000 | SvelteKit 프론트엔드 |

### 4단계: 접속 확인

```bash
# 백엔드 헬스 체크
curl http://localhost:8000/api/health

# 프론트엔드 접속
open http://localhost:3000
```

### 서비스 상태 확인 및 로그

```bash
# 전체 서비스 상태
docker compose ps

# 백엔드 로그
docker compose logs -f backend

# 프론트엔드 로그
docker compose logs -f frontend
```

### 서비스 중지

```bash
docker compose down
```

---

## union.toml 설정 상세

### `[openstack]` 섹션

```toml
[openstack]
auth_url = "http://keystone.example.com:5000/v3"
project_name = "admin"
project_domain_name = "Default"
user_domain_name = "Default"
region_name = "RegionOne"

manila_endpoint = ""
manila_share_network_id = ""
manila_share_type = "cephfstype"
ceph_monitors = "192.168.1.10:6789,192.168.1.11:6789"
```

| 키 | 필수 | 설명 |
|----|------|------|
| `auth_url` | 필수 | Keystone v3 엔드포인트. 일반적으로 `:5000/v3` |
| `project_name` | 필수 | 기본 OpenStack 프로젝트 이름 |
| `project_domain_name` | 필수 | 프로젝트 도메인 (대부분 `Default`) |
| `user_domain_name` | 필수 | 사용자 도메인 (대부분 `Default`) |
| `region_name` | 필수 | OpenStack 리전 이름 |
| `manila_endpoint` | 선택 | Manila API URL 직접 지정. 서비스 카탈로그가 올바르면 비워두세요. |
| `manila_share_network_id` | 필수 (Manila 사용 시) | VM에서 CephFS share에 접근할 네트워크 UUID |
| `manila_share_type` | 필수 (Manila 사용 시) | Manila share 타입 이름 |
| `ceph_monitors` | 필수 (Manila 사용 시) | CephFS 모니터 주소 목록 (콤마 구분). cloud-init이 마운트 명령에 사용합니다. |

### `[app]` 섹션

```toml
[app]
backend_port = 8000
frontend_port = 3000
secret_key = "change-me-in-production"
refresh_interval_ms = 5000
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `backend_port` | 8000 | FastAPI 리슨 포트 |
| `frontend_port` | 3000 | SvelteKit 리슨 포트 |
| `secret_key` | — | 세션 서명 키. **운영 환경에서 반드시 강력한 랜덤 값으로 교체하세요.** |
| `refresh_interval_ms` | 5000 | 대시보드 자동 새로고침 간격 밀리초 (3000~30000 권장) |

### `[cache]` 섹션

```toml
[cache]
redis_url = "redis://redis:6379/0"
default_ttl_seconds = 30
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `redis_url` | `redis://redis:6379/0` | Redis 연결 URL. Docker Compose 내부에서는 `redis` 호스트명을 사용합니다. 외부 Redis 사용 시 변경하세요. |
| `default_ttl_seconds` | 30 | OpenStack API 응답 기본 캐시 유지 시간 (초) |

### `[nova]` 섹션

```toml
[nova]
default_network_id = ""
default_availability_zone = "nova"
boot_volume_size_gb = 20
upper_volume_size_gb = 50
```

| 키 | 기본값 | 설명 |
|----|--------|------|
| `default_network_id` | — | VM 생성 시 네트워크를 지정하지 않을 때 사용할 기본 네트워크 UUID |
| `default_availability_zone` | `nova` | 기본 Nova / Cinder 가용 영역 |
| `boot_volume_size_gb` | 20 | 부트 볼륨 기본 크기 (GB) |
| `upper_volume_size_gb` | 50 | OverlayFS upperdir 볼륨 크기 (GB). 사용자 작업 파일 저장 공간입니다. |

---

## 환경변수

`docker-compose.yml`에서 프론트엔드 서비스에 환경변수를 통해 추가 설정을 주입할 수 있습니다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ORIGIN` | `http://localhost:3000` | SvelteKit CSRF 보호용 출처 URL. 운영 도메인으로 변경 필요. |
| `PUBLIC_API_BASE` | `http://localhost:8000` | 브라우저에서 백엔드 API로 요청하는 기본 URL. 운영 시 실제 API 도메인으로 변경. |

운영 예시:

```yaml
environment:
  - ORIGIN=https://union.example.com
  - PUBLIC_API_BASE=https://api.union.example.com
```

---

## 모니터링 스택 설치

OpenSearch, Prometheus, Grafana는 Docker Compose 프로필로 분리되어 있습니다. 별도 명령으로 활성화합니다.

```bash
docker compose --profile monitoring up -d
```

| 서비스 | 포트 | 접속 URL |
|--------|------|----------|
| OpenSearch | 9200 | http://localhost:9200 |
| OpenSearch Dashboards | 5601 | http://localhost:5601 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3001 | http://localhost:3001 |

Grafana 초기 계정: `admin` / `admin`

### Prometheus 스크레이핑 설정

`monitoring/prometheus.yml`에서 Union 백엔드 메트릭 엔드포인트를 스크레이핑하도록 설정합니다.

```yaml
scrape_configs:
  - job_name: 'union'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /api/metrics
```

### Grafana 대시보드

`monitoring/grafana/provisioning/` 디렉토리에 데이터소스와 대시보드 프로비저닝 설정이 포함되어 있습니다. Grafana 시작 시 자동으로 로드됩니다.

---

## 운영 환경 체크리스트

운영 환경에 배포하기 전에 다음 항목을 반드시 확인하세요.

### 보안

- [ ] `union.toml`의 `secret_key`를 강력한 랜덤 값으로 교체
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] `ORIGIN` 환경변수를 실제 운영 도메인으로 설정
- [ ] `PUBLIC_API_BASE`를 실제 API 도메인으로 설정
- [ ] Redis 포트(6379)를 외부에 노출하지 않도록 방화벽 설정
- [ ] 백엔드 API에 HTTPS 역방향 프록시(Nginx, Caddy 등) 적용
- [ ] Grafana 초기 비밀번호 변경 (`GF_SECURITY_ADMIN_PASSWORD` 환경변수)

### 안정성

- [ ] Docker 볼륨 데이터 백업 전략 수립 (Redis AOF, OpenSearch 스냅샷)
- [ ] `docker compose` 재시작 정책 확인 (`restart: unless-stopped` 기본 적용)
- [ ] `/api/health` 엔드포인트를 외부 모니터링 시스템에 연결
- [ ] 로그 로테이션 확인 (Docker `json-file` 드라이버 `max-size` / `max-file` 기본 설정)

### 성능

- [ ] `refresh_interval_ms`를 네트워크 환경에 맞게 조정 (OpenStack API 부하 고려)
- [ ] Redis `default_ttl_seconds` 튜닝 (짧을수록 최신 데이터, 길수록 낮은 API 부하)
- [ ] 대규모 환경에서 Redis 메모리 한도 설정 (`maxmemory` 옵션)

---

## Kubernetes 배포

Kubernetes 매니페스트는 `k8s/` 디렉토리에 있습니다.

```
k8s/
├── namespace.yaml
├── configmap.yaml     # union.toml 내용을 ConfigMap으로 관리
├── secret.yaml        # OpenStack 자격증명 Secret
├── redis/
├── backend/
└── frontend/
```

기본 배포:

```bash
# 네임스페이스 및 설정 생성
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 서비스 배포
kubectl apply -f k8s/redis/
kubectl apply -f k8s/backend/
kubectl apply -f k8s/frontend/

# 상태 확인
kubectl -n union get pods
```

자세한 Kubernetes 배포 옵션(Ingress, HPA, PVC 등)은 `k8s/` 디렉토리 내 각 매니페스트 파일의 주석을 참고하세요.
