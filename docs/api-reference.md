# Union API 레퍼런스

Union 백엔드는 FastAPI로 구현된 REST API이며, 모든 OpenStack 서비스와 통신하는 단일 게이트웨이 역할을 합니다.

---

## 인증 헤더

인증이 필요한 모든 엔드포인트에 다음 헤더를 포함해야 합니다.

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 (`/api/auth/login` 응답에서 획득) |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

`/api/auth/login`, `/api/health`, `/api/metrics`는 토큰이 필요하지 않습니다.

---

## API 태그별 문서

### 인증 및 사용자

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [인증 (Auth)](api/auth.md) | `auth` | `/api/auth` | Keystone 토큰 발급, 프로젝트 조회, 스코프 전환 |
| [프로필 (Profile)](api/profile.md) | `profile` | `/api/profile` | 사용자 프로필 조회, 비밀번호 변경 |

### 관리자

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [관리자 (Admin)](api/admin.md) | `admin`, `admin-services`, `admin-flavors`, `admin-identity`, `admin-gpu` | `/api/admin` | 클러스터 개요, 사용자/프로젝트/쿼터/그룹/역할 관리, Flavor 관리, GPU 모니터링, 서비스 상태, 볼륨/네트워크 관리 |

### 컴퓨트

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [이미지 (Images)](api/images.md) | `images` | `/api/images` | Glance 이미지 카탈로그 조회 |
| [플레이버 (Flavors)](api/flavors.md) | `flavors` | `/api/flavors` | Nova 플레이버 목록 조회 |
| [인스턴스 (Instances)](api/instances.md) | `instances` | `/api/instances` | VM 생성/조회/제어/삭제, OverlayFS 생성 (SSE), 볼륨/인터페이스/보안그룹 관리 |
| [키페어 (Keypairs)](api/keypairs.md) | `keypairs` | `/api/keypairs` | SSH 키페어 생성/삭제 |

### 스토리지

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [볼륨 (Volumes)](api/volumes.md) | `volumes`, `volume-backups`, `volume-snapshots` | `/api/volumes`, `/api/volume-snapshots` | Cinder 볼륨, 백업, 스냅샷 관리 |
| [파일 스토리지 (File Storage)](api/file-storage.md) | `file-storage` | `/api/file-storage` | Manila CephFS 공유 파일시스템, 접근 규칙 (선택 서비스) |

### 네트워크

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [네트워크 (Networks)](api/networks.md) | `networks` | `/api/networks` | Neutron 네트워크, 서브넷, Floating IP, 토폴로지 |
| [라우터 (Routers)](api/routers.md) | `routers` | `/api/routers` | Neutron 라우터, 인터페이스, 게이트웨이 |
| [로드밸런서 (Load Balancers)](api/loadbalancers.md) | `loadbalancers` | `/api/loadbalancers` | Octavia 로드밸런서, 리스너, 풀, 멤버, 헬스 모니터 |
| [보안 그룹 (Security Groups)](api/security-groups.md) | `security-groups` | `/api/security-groups` | Neutron 보안 그룹, 규칙 관리 |

### 컨테이너 (선택 서비스)

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [컨테이너 (Containers)](api/containers.md) | `clusters`, `containers` | `/api/clusters`, `/api/containers` | Magnum 쿠버네티스 클러스터, Zun 컨테이너 (config.toml에서 활성화 필요) |

### 대시보드 및 공통

| 문서 | 태그 | 기본 경로 | 설명 |
|------|------|-----------|------|
| [대시보드 (Dashboard)](api/dashboard.md) | `dashboard`, `libraries`, `site`, `user-dashboard` | `/api/dashboard`, `/api/libraries`, `/api/site-config`, `/api/user-dashboard` | 프로젝트 리소스 요약, 라이브러리 카탈로그, 사이트 설정 |
| [메트릭 (Metrics)](api/metrics.md) | `metrics` | `/api/metrics`, `/api/health` | Prometheus 메트릭, 헬스 체크 (인증 불필요) |

---

## 전체 엔드포인트 빠른 참조

### 인증 `/api/auth`

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `POST` | `/api/auth/login` | 없음 | Keystone 토큰 발급 |
| `GET` | `/api/auth/me` | 필요 | 현재 사용자 정보 |
| `GET` | `/api/auth/projects` | 필요 | 접근 가능한 프로젝트 목록 |
| `POST` | `/api/auth/token` | 필요 | 프로젝트 스코프 전환 |

### 프로필 `/api/profile`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/profile` | 사용자 프로필 정보 |
| `PUT` | `/api/profile/password` | 비밀번호 변경 |

### 관리자 `/api/admin`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/admin/overview` | 클러스터 전체 개요 |
| `GET` | `/api/admin/hypervisors` | 하이퍼바이저 목록 |
| `GET` | `/api/admin/overview/projects` | 프로젝트별 리소스 사용량 |
| `GET` | `/api/admin/file-storage` | 전체 파일 스토리지 목록 |
| `POST` | `/api/admin/file-storage/build` | 사전 빌드 share 생성 |
| `GET` | `/api/admin/all-instances` | 전체 인스턴스 (페이지네이션) |
| `GET` | `/api/admin/all-volumes` | 전체 볼륨 (페이지네이션) |
| `GET` | `/api/admin/all-containers` | 전체 컨테이너 |
| `GET` | `/api/admin/all-file-storages` | 전체 파일 스토리지 |
| `GET` | `/api/admin/all-networks` | 전체 네트워크 |
| `GET` | `/api/admin/all-floating-ips` | 전체 Floating IP |
| `GET` | `/api/admin/all-routers` | 전체 라우터 |
| `GET` | `/api/admin/all-ports` | 전체 포트 |
| `GET` | `/api/admin/topology` | 전체 토폴로지 |
| `GET` | `/api/admin/timeseries/{type}` | 시계열 데이터 |
| `GET` | `/api/admin/services` | 서비스 상태 모니터링 |
| `GET` | `/api/admin/gpu-hosts` | GPU 호스트 모니터링 |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/admin/flavors/...` | Flavor 관리 |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/admin/users/...` | 사용자 관리 |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/admin/projects/...` | 프로젝트 관리 |
| `GET`/`PUT` | `/api/admin/quotas/{project_id}` | 쿼터 관리 |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/admin/groups/...` | 그룹 관리 |
| `GET`/`POST`/`DELETE` | `/api/admin/roles/...` | 역할 관리 |
| `PATCH`/`DELETE`/`POST` | `/api/admin/volumes/{id}/...` | 관리자 볼륨 관리 |
| `POST`/`PUT`/`DELETE` | `/api/admin/networks/...` | 관리자 네트워크 관리 |
| `POST`/`DELETE` | `/api/admin/floating-ips/...` | 관리자 Floating IP 관리 |
| `POST`/`PUT`/`DELETE` | `/api/admin/routers/...` | 관리자 라우터 관리 |
| `PUT`/`DELETE` | `/api/admin/ports/...` | 관리자 포트 관리 |

### 이미지 `/api/images`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/images` | Glance 이미지 목록 (300초 캐시) |

### 플레이버 `/api/flavors`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/flavors` | Nova 플레이버 목록 |

### 인스턴스 `/api/instances`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances` | 인스턴스 목록 (15초 캐시) |
| `GET` | `/api/instances/{id}` | 인스턴스 상세 |
| `POST` | `/api/instances` | 동기 생성 |
| `POST` | `/api/instances/async` | SSE 비동기 생성 |
| `DELETE` | `/api/instances/{id}` | 삭제 |
| `POST` | `/api/instances/{id}/start` | 시작 |
| `POST` | `/api/instances/{id}/stop` | 중지 |
| `POST` | `/api/instances/{id}/reboot` | 재시작 |
| `GET` | `/api/instances/{id}/console` | VNC 콘솔 URL |
| `GET` | `/api/instances/{id}/log` | 콘솔 로그 |
| `GET` | `/api/instances/{id}/owner` | 소유자 정보 |
| `GET`/`POST`/`DELETE` | `/api/instances/{id}/volumes/...` | 볼륨 관리 |
| `GET`/`POST`/`DELETE` | `/api/instances/{id}/interfaces/...` | 네트워크 인터페이스 |
| `GET`/`POST` | `/api/instances/{id}/security-groups` | 보안 그룹 |
| `POST` | `/api/instances/{id}/ports/{pid}/security-groups` | 포트 보안 그룹 업데이트 |

### 키페어 `/api/keypairs`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/keypairs` | 키페어 목록 |
| `POST` | `/api/keypairs` | 키페어 생성 |
| `DELETE` | `/api/keypairs/{name}` | 키페어 삭제 |

### 볼륨 `/api/volumes`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volumes` | 볼륨 목록 (15초 캐시) |
| `GET` | `/api/volumes/{id}` | 볼륨 상세 |
| `POST` | `/api/volumes` | 볼륨 생성 |
| `DELETE` | `/api/volumes/{id}` | 볼륨 삭제 |
| `GET` | `/api/volumes/backups` | 백업 목록 |
| `GET` | `/api/volumes/backups/{id}` | 백업 상세 |
| `POST` | `/api/volumes/backups` | 백업 생성 |
| `POST` | `/api/volumes/backups/{id}/restore` | 백업 복원 |
| `DELETE` | `/api/volumes/backups/{id}` | 백업 삭제 |

### 볼륨 스냅샷 `/api/volume-snapshots`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volume-snapshots` | 스냅샷 목록 |
| `GET` | `/api/volume-snapshots/{id}` | 스냅샷 상세 |
| `POST` | `/api/volume-snapshots` | 스냅샷 생성 |
| `DELETE` | `/api/volume-snapshots/{id}` | 스냅샷 삭제 |

### 파일 스토리지 `/api/file-storage` (선택 서비스)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/file-storage` | 파일 스토리지 목록 |
| `GET` | `/api/file-storage/quota` | 쿼터 조회 |
| `GET` | `/api/file-storage/types` | share 타입 목록 |
| `GET` | `/api/file-storage/{id}` | 상세 |
| `POST` | `/api/file-storage` | 생성 (분당 5회 제한) |
| `DELETE` | `/api/file-storage/{id}` | 삭제 |
| `GET` | `/api/file-storage/{id}/access-rules` | 접근 규칙 목록 |
| `POST` | `/api/file-storage/{id}/access-rules` | 접근 규칙 추가 |
| `DELETE` | `/api/file-storage/{id}/access-rules/{aid}` | 접근 규칙 삭제 |

### 네트워크 `/api/networks`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/networks` | 네트워크 목록 |
| `POST` | `/api/networks` | 네트워크 생성 |
| `GET` | `/api/networks/topology` | 토폴로지 (30초 캐시) |
| `GET` | `/api/networks/{id}` | 네트워크 상세 |
| `DELETE` | `/api/networks/{id}` | 삭제 |
| `POST` | `/api/networks/{id}/subnets` | 서브넷 생성 |
| `DELETE` | `/api/networks/subnets/{id}` | 서브넷 삭제 |
| `GET` | `/api/networks/floating-ips` | Floating IP 목록 |
| `POST` | `/api/networks/floating-ips` | Floating IP 생성 |
| `POST` | `/api/networks/floating-ips/{id}/associate` | 연결 |
| `POST` | `/api/networks/floating-ips/{id}/disassociate` | 해제 |
| `DELETE` | `/api/networks/floating-ips/{id}` | 삭제 |

### 라우터 `/api/routers`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/routers` | 목록 (30초 캐시) |
| `POST` | `/api/routers` | 생성 |
| `GET` | `/api/routers/{id}` | 상세 (인터페이스 포함) |
| `DELETE` | `/api/routers/{id}` | 삭제 |
| `POST` | `/api/routers/{id}/interfaces` | 인터페이스 추가 |
| `DELETE` | `/api/routers/{id}/interfaces/{sid}` | 인터페이스 제거 |
| `POST` | `/api/routers/{id}/gateway` | 게이트웨이 설정 |
| `DELETE` | `/api/routers/{id}/gateway` | 게이트웨이 제거 |

### 로드밸런서 `/api/loadbalancers`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers` | 목록 (30초 캐시) |
| `POST` | `/api/loadbalancers` | 생성 |
| `GET` | `/api/loadbalancers/{id}` | 상세 |
| `DELETE` | `/api/loadbalancers/{id}` | 삭제 |
| `GET` | `/api/loadbalancers/{id}/listeners` | 리스너 목록 |
| `POST` | `/api/loadbalancers/{id}/listeners` | 리스너 생성 |
| `DELETE` | `/api/loadbalancers/{id}/listeners/{lid}` | 리스너 삭제 |
| `GET` | `/api/loadbalancers/{id}/pools` | 풀 목록 |
| `POST` | `/api/loadbalancers/{id}/pools` | 풀 생성 |
| `DELETE` | `/api/loadbalancers/{id}/pools/{pid}` | 풀 삭제 |
| `GET` | `/api/loadbalancers/{id}/pools/{pid}/members` | 멤버 목록 |
| `POST` | `/api/loadbalancers/{id}/pools/{pid}/members` | 멤버 추가 |
| `DELETE` | `/api/loadbalancers/{id}/pools/{pid}/members/{mid}` | 멤버 제거 |
| `GET` | `/api/loadbalancers/{id}/pools/{pid}/health-monitor` | 헬스 모니터 |
| `POST` | `/api/loadbalancers/{id}/pools/{pid}/health-monitor` | 헬스 모니터 생성 |
| `DELETE` | `/api/loadbalancers/{id}/pools/{pid}/health-monitor/{hid}` | 헬스 모니터 삭제 |

### 보안 그룹 `/api/security-groups`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/security-groups` | 목록 (60초 캐시) |
| `POST` | `/api/security-groups` | 생성 |
| `DELETE` | `/api/security-groups/{id}` | 삭제 |
| `POST` | `/api/security-groups/{id}/rules` | 규칙 추가 |
| `DELETE` | `/api/security-groups/{id}/rules/{rid}` | 규칙 삭제 |

### 대시보드 `/api/dashboard`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/dashboard/summary` | 리소스 요약 |
| `GET` | `/api/dashboard/config` | 프론트엔드 설정 |

### 라이브러리 `/api/libraries`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/libraries` | 라이브러리 카탈로그 |
| `GET` | `/api/libraries/shares` | 사전 빌드 share 목록 |

### 사이트 설정 `/api/site-config`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/site-config` | 전역 사이트 설정 |

### 사용자 대시보드 `/api/user-dashboard`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/user-dashboard` | 사용자 개인 리소스 요약 |

### 컨테이너 `/api/clusters`, `/api/containers` (선택 서비스)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/clusters` | 쿠버네티스 클러스터 목록 |
| `POST` | `/api/clusters` | 클러스터 생성 |
| `GET` | `/api/clusters/{id}` | 클러스터 상세 |
| `DELETE` | `/api/clusters/{id}` | 클러스터 삭제 |
| `GET` | `/api/containers` | Zun 컨테이너 목록 |
| `POST` | `/api/containers` | 컨테이너 생성 |
| `GET` | `/api/containers/{id}` | 컨테이너 상세 |
| `DELETE` | `/api/containers/{id}` | 컨테이너 삭제 |
| `POST` | `/api/containers/{id}/start` | 시작 |
| `POST` | `/api/containers/{id}/stop` | 중지 |
| `POST` | `/api/containers/{id}/restart` | 재시작 |

### 메트릭 및 헬스 체크

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `GET` | `/api/metrics` | 없음 | Prometheus 메트릭 |
| `GET` | `/api/health` | 없음 | 서비스 헬스 체크 |