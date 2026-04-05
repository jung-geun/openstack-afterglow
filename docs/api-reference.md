# Union API 레퍼런스

## 인증 헤더

인증이 필요한 모든 엔드포인트에 다음 헤더를 포함해야 합니다.

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 (`/api/auth/login` 응답에서 획득) |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

`/api/auth/login`과 `/api/health`는 토큰이 필요하지 않습니다.

---

## 1. 인증 `/api/auth`

| 메서드 | 경로 | 인증 필요 | 설명 |
|--------|------|-----------|------|
| `POST` | `/api/auth/login` | 없음 | 사용자 이름/비밀번호로 Keystone 토큰 발급 |
| `GET` | `/api/auth/me` | 필요 | 현재 토큰의 사용자/프로젝트 정보 반환 |
| `GET` | `/api/auth/session-info` | 필요 | 세션 남은 시간(초) 및 타임아웃 설정 반환 |
| `POST` | `/api/auth/extend-session` | 필요 | 세션 시작 시간 재설정으로 세션 연장 |
| `GET` | `/api/auth/projects` | 필요 | 사용자가 접근 가능한 프로젝트 목록 반환 |

### POST /api/auth/login

```json
{
  "username": "string",
  "password": "string",
  "project_name": "string (선택)",
  "domain_name": "string (선택, 기본 Default)"
}
```

**응답 (200)**

```json
{
  "token": "string",
  "project_id": "string",
  "project_name": "string",
  "user_id": "string",
  "username": "string",
  "expires_at": "2024-01-01T00:00:00Z"
}
```

---

## 2. 이미지 `/api/images`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/images` | Glance 이미지 목록 반환 (300초 캐시) |

**응답 항목 (ImageInfo)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 이미지 UUID |
| `name` | string | 이미지 이름 |
| `status` | string | 상태 (active 등) |
| `size` | integer | 바이트 단위 크기 |
| `min_disk` | integer | 최소 디스크 GB |
| `min_ram` | integer | 최소 RAM MB |
| `disk_format` | string | 디스크 포맷 (qcow2 등) |
| `os_distro` | string | OS 배포판 |
| `created_at` | string | 생성 일시 |

---

## 3. 플레이버 `/api/flavors`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/flavors` | Nova 플레이버 목록 반환 |

**응답 항목 (FlavorInfo)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 플레이버 UUID |
| `name` | string | 플레이버 이름 |
| `vcpus` | integer | vCPU 수 |
| `ram` | integer | RAM (MB) |
| `disk` | integer | 루트 디스크 (GB) |
| `is_public` | boolean | 공개 여부 |
| `extra_specs` | object | 추가 스펙 (GPU 정보 포함) |

---

## 4. 라이브러리 `/api/libraries`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/libraries` | 라이브러리 카탈로그 목록 (사전 빌드 share 가용 여부 포함) |
| `GET` | `/api/libraries/shares` | 사전 빌드된 Manila share 목록 |

**응답 항목 (LibraryConfig)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 라이브러리 식별자 (예: `python311`) |
| `name` | string | 라이브러리 표시명 |
| `version` | string | 버전 |
| `packages` | array[string] | pip 패키지 목록 |
| `depends_on` | array[string] | 의존하는 다른 라이브러리 ID |
| `share_id` | string\|null | 사전 빌드 share UUID |
| `available_prebuilt` | boolean | 사전 빌드 share 가용 여부 |

---

## 5. 인스턴스 `/api/instances`

### 기본 CRUD

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances` | 인스턴스 목록 (15초 캐시) |
| `GET` | `/api/instances/{instance_id}` | 특정 인스턴스 상세 정보 |
| `POST` | `/api/instances` | 인스턴스 동기 생성 |
| `POST` | `/api/instances/async` | 인스턴스 SSE 비동기 생성 |
| `DELETE` | `/api/instances/{instance_id}` | 인스턴스 삭제 (연관 리소스 포함) |

### 인스턴스 제어

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/instances/{instance_id}/start` | 인스턴스 시작 |
| `POST` | `/api/instances/{instance_id}/stop` | 인스턴스 중지 |
| `POST` | `/api/instances/{instance_id}/reboot` | 인스턴스 재시작 |
| `GET` | `/api/instances/{instance_id}/console` | VNC 콘솔 URL 반환 |
| `GET` | `/api/instances/{instance_id}/log` | 콘솔 로그 반환 (`?length=100`) |
| `GET` | `/api/instances/{instance_id}/owner` | 인스턴스 소유자 정보 반환 |

### 볼륨 관리

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/volumes` | 연결된 볼륨 목록 |
| `POST` | `/api/instances/{instance_id}/volumes` | 볼륨 연결 (`{"volume_id": "..."}`) |
| `DELETE` | `/api/instances/{instance_id}/volumes/{volume_id}` | 볼륨 해제 |

### 네트워크 인터페이스

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/interfaces` | 네트워크 인터페이스 목록 |
| `POST` | `/api/instances/{instance_id}/interfaces` | 인터페이스 추가 (`{"net_id": "..."}`) |
| `DELETE` | `/api/instances/{instance_id}/interfaces/{port_id}` | 인터페이스 제거 |

### 보안 그룹

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/security-groups` | 인스턴스의 포트 및 보안 그룹 목록 |
| `POST` | `/api/instances/{instance_id}/ports/{port_id}/security-groups` | 포트 보안 그룹 업데이트 (`{"security_group_ids": [...]}`) |

### POST /api/instances (동기) 및 /api/instances/async (SSE) 요청 본문

```json
{
  "name": "string",
  "image_id": "string",
  "flavor_id": "string",
  "libraries": ["python311", "pytorch"],
  "strategy": "prebuilt",
  "network_id": "string (선택)",
  "key_name": "string (선택)",
  "admin_pass": "string (선택)",
  "availability_zone": "string (선택)",
  "boot_volume_size_gb": 20
}
```

**strategy 값**: `prebuilt` (사전 빌드 share 사용) 또는 `dynamic` (전용 share 신규 생성)

### SSE 이벤트 형식 (`/api/instances/async`)

```json
{
  "step": "MANILA_PREPARING | BOOT_VOLUME_CREATING | UPPER_VOLUME_CREATING | USERDATA_GENERATING | SERVER_CREATING | ATTACHING_VOLUME | FLOATING_IP_CREATING | COMPLETED | FAILED",
  "progress": 0,
  "message": "string",
  "instance_id": "string (COMPLETED 시)",
  "error": "string (FAILED 시)"
}
```

---

## 6. 관리자 `/api/admin`

관리자 권한이 필요합니다.

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/admin/shares` | 전체 Union 관련 share 목록 (prebuilt + dynamic) |
| `POST` | `/api/admin/shares/build` | 사전 빌드 share 생성 트리거 (`?library_id=python311`) |

### POST /api/admin/shares/build 응답

```json
{
  "share_id": "string",
  "status": "building",
  "library": "string"
}
```

---

## 7. 볼륨 `/api/volumes`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volumes` | 볼륨 목록 (15초 캐시) |
| `GET` | `/api/volumes/{volume_id}` | 볼륨 상세 정보 |
| `POST` | `/api/volumes` | 볼륨 생성 |
| `DELETE` | `/api/volumes/{volume_id}` | 볼륨 삭제 |

### POST /api/volumes 요청 본문

```json
{
  "name": "string",
  "size_gb": 50,
  "availability_zone": "string (선택)"
}
```

**응답 항목 (VolumeInfo)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 볼륨 UUID |
| `name` | string | 볼륨 이름 |
| `status` | string | 상태 (available, in-use 등) |
| `size` | integer | 크기 (GB) |
| `volume_type` | string | 볼륨 타입 |
| `attachments` | array | 연결 정보 |

---

## 8. 공유 파일시스템 `/api/shares`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/shares` | Manila share 목록 (15초 캐시) |
| `GET` | `/api/shares/{share_id}` | share 상세 정보 |
| `POST` | `/api/shares` | share 생성 |
| `DELETE` | `/api/shares/{share_id}` | share 삭제 |

### POST /api/shares 요청 본문

```json
{
  "name": "string",
  "size_gb": 20,
  "share_type": "cephfstype",
  "share_network_id": "string (선택)",
  "metadata": {}
}
```

**응답 항목 (ShareInfo)**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | Share UUID |
| `name` | string | Share 이름 |
| `status` | string | 상태 |
| `size` | integer | 크기 (GB) |
| `share_proto` | string | 프로토콜 (CEPHFS 등) |
| `export_locations` | array[string] | 마운트 경로 목록 |
| `metadata` | object | 메타데이터 |
| `library_name` | string | Union 라이브러리 ID |

---

## 9. 네트워크 `/api/networks`

### 네트워크

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/networks` | 네트워크 목록 |
| `POST` | `/api/networks` | 네트워크 생성 (`{"name": "string"}`) |
| `GET` | `/api/networks/topology` | 네트워크 토폴로지 전체 (30초 캐시) |
| `GET` | `/api/networks/{network_id}` | 네트워크 상세 (서브넷, 라우터 포함) |
| `DELETE` | `/api/networks/{network_id}` | 네트워크 삭제 |

### 서브넷

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/networks/{network_id}/subnets` | 서브넷 생성 |
| `DELETE` | `/api/networks/subnets/{subnet_id}` | 서브넷 삭제 |

### POST /api/networks/{network_id}/subnets 요청 본문

```json
{
  "name": "string",
  "cidr": "192.168.1.0/24",
  "gateway_ip": "string (선택)",
  "enable_dhcp": true
}
```

### Floating IP

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/networks/floating-ips` | Floating IP 목록 |
| `POST` | `/api/networks/floating-ips` | Floating IP 생성 (`{"floating_network_id": "..."}`) |
| `POST` | `/api/networks/floating-ips/{fip_id}/associate` | Floating IP 인스턴스 연결 (`{"instance_id": "..."}`) |
| `POST` | `/api/networks/floating-ips/{fip_id}/disassociate` | Floating IP 해제 |
| `DELETE` | `/api/networks/floating-ips/{fip_id}` | Floating IP 삭제 |

---

## 10. 키페어 `/api/keypairs`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/keypairs` | 키페어 목록 |
| `POST` | `/api/keypairs` | 키페어 생성 |
| `DELETE` | `/api/keypairs/{keypair_name}` | 키페어 삭제 |

### POST /api/keypairs 요청 본문

```json
{
  "name": "string",
  "public_key": "string (선택, 없으면 Nova가 생성)",
  "key_type": "ssh"
}
```

---

## 11. 대시보드 `/api/dashboard`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/dashboard/summary` | 인스턴스 수, 컴퓨트/스토리지 한도, GPU 사용량 |
| `GET` | `/api/dashboard/config` | 프론트엔드 설정 (새로고침 간격 등) |

### GET /api/dashboard/summary 응답

```json
{
  "instances": {
    "total": 10,
    "active": 8,
    "shutoff": 1,
    "error": 1
  },
  "compute": { "...nova limits..." },
  "storage": { "...cinder limits..." },
  "gpu_used": 4
}
```

---

## 12. 라우터 `/api/routers`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/routers` | 라우터 목록 (30초 캐시) |
| `POST` | `/api/routers` | 라우터 생성 |
| `GET` | `/api/routers/{router_id}` | 라우터 상세 (연결된 인터페이스 포함) |
| `DELETE` | `/api/routers/{router_id}` | 라우터 삭제 |
| `POST` | `/api/routers/{router_id}/interfaces` | 서브넷 인터페이스 추가 (`{"subnet_id": "..."}`) |
| `DELETE` | `/api/routers/{router_id}/interfaces/{subnet_id}` | 인터페이스 제거 |
| `POST` | `/api/routers/{router_id}/gateway` | 외부 게이트웨이 설정 (`{"external_network_id": "..."}`) |
| `DELETE` | `/api/routers/{router_id}/gateway` | 게이트웨이 제거 |

### POST /api/routers 요청 본문

```json
{
  "name": "string",
  "external_network_id": "string (선택)"
}
```

---

## 13. 로드밸런서 `/api/loadbalancers`

### 로드밸런서

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers` | 로드밸런서 목록 (30초 캐시) |
| `POST` | `/api/loadbalancers` | 로드밸런서 생성 |
| `GET` | `/api/loadbalancers/{lb_id}` | 로드밸런서 상세 |
| `DELETE` | `/api/loadbalancers/{lb_id}` | 로드밸런서 삭제 |

### POST /api/loadbalancers 요청 본문

```json
{
  "name": "string",
  "vip_subnet_id": "string",
  "description": "string (선택)"
}
```

### 리스너

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/listeners` | 리스너 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/listeners` | 리스너 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/listeners/{listener_id}` | 리스너 삭제 |

### POST /api/loadbalancers/{lb_id}/listeners 요청 본문

```json
{
  "protocol": "HTTP",
  "protocol_port": 80,
  "name": "string (선택)",
  "default_pool_id": "string (선택)"
}
```

### 풀

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools` | 풀 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/pools` | 풀 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}` | 풀 삭제 |

### POST /api/loadbalancers/{lb_id}/pools 요청 본문

```json
{
  "protocol": "HTTP",
  "lb_algorithm": "ROUND_ROBIN",
  "name": "string (선택)",
  "listener_id": "string (선택)"
}
```

### 멤버

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members` | 멤버 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members` | 멤버 추가 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members/{member_id}` | 멤버 제거 |

### POST .../members 요청 본문

```json
{
  "address": "192.168.1.10",
  "protocol_port": 8080,
  "subnet_id": "string (선택)",
  "name": "string (선택)",
  "weight": 1
}
```

### 헬스 모니터

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor` | 헬스 모니터 조회 |
| `POST` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor` | 헬스 모니터 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor/{hm_id}` | 헬스 모니터 삭제 |

### POST .../health-monitor 요청 본문

```json
{
  "type": "HTTP",
  "delay": 5,
  "timeout": 5,
  "max_retries": 3,
  "name": "string (선택)"
}
```

---

## 14. 보안 그룹 `/api/security-groups`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/security-groups` | 보안 그룹 목록 (60초 캐시) |
| `POST` | `/api/security-groups` | 보안 그룹 생성 |
| `DELETE` | `/api/security-groups/{sg_id}` | 보안 그룹 삭제 |
| `POST` | `/api/security-groups/{sg_id}/rules` | 보안 그룹 규칙 추가 |
| `DELETE` | `/api/security-groups/{sg_id}/rules/{rule_id}` | 보안 그룹 규칙 삭제 |

### POST /api/security-groups 요청 본문

```json
{
  "name": "string",
  "description": "string (선택)"
}
```

### POST /api/security-groups/{sg_id}/rules 요청 본문

```json
{
  "direction": "ingress",
  "protocol": "tcp",
  "port_range_min": 22,
  "port_range_max": 22,
  "remote_ip_prefix": "0.0.0.0/0",
  "ethertype": "IPv4"
}
```

| 필드 | 허용 값 |
|------|---------|
| `direction` | `ingress`, `egress` |
| `protocol` | `tcp`, `udp`, `icmp`, `null` (모든 프로토콜) |
| `ethertype` | `IPv4`, `IPv6` |

---

## 15. 메트릭 `/api/metrics`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/metrics` | Prometheus exposition 포맷 메트릭 반환 |

인증 불필요. Prometheus가 이 엔드포인트를 스크레이핑합니다.

**수집 메트릭**

| 메트릭 | 타입 | 레이블 | 설명 |
|--------|------|--------|------|
| `union_http_requests_total` | Counter | method, path, status | 총 HTTP 요청 수 |
| `union_http_request_duration_ms` | Histogram | method, path | 요청 처리 시간 (ms) |

---

## 16. 헬스 체크 `/api/health`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/health` | 서비스 정상 여부 확인 |

인증 불필요. 로드밸런서 헬스 체크 및 Docker Compose healthcheck에 사용합니다.
