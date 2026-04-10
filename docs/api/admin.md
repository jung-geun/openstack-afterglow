# 관리자 (Admin) API

> 태그: `admin`, `admin-services`, `admin-flavors`, `admin-identity`, `admin-gpu`  
> 기본 경로: `/api/admin`

모든 관리자 API는 관리자 권한이 필요합니다. 인증 헤더와 함께 관리자 역할이 부여된 토큰을 사용해야 합니다.

---

## 인증 및 권한

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | 관리자 권한이 있는 Keystone 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

모든 엔드포인트에 `require_admin` 의존성이 적용되어 있어, 관리자가 아닌 사용자는 `403 Forbidden` 응답을 받습니다.

---

## 목차

1. [개요 및 리소스 집계](#1-개요-및-리소스-집계)
2. [파일 스토리지 관리](#2-파일-스토리지-관리)
3. [인스턴스/볼륨/네트워크 전체 조회](#3-인스턴스볼륨네트워크-전체-조회)
4. [토폴로지 및 시계열](#4-토폴로지-및-시계열)
5. [볼륨 관리](#5-볼륨-관리)
6. [네트워크 관리](#6-네트워크-관리)
7. [서비스 상태 모니터링](#7-서비스-상태-모니터링)
8. [Flavor 관리](#8-flavor-관리)
9. [사용자 관리](#9-사용자-관리)
10. [프로젝트 관리](#10-프로젝트-관리)
11. [쿼터 관리](#11-쿼터-관리)
12. [그룹 관리](#12-그룹-관리)
13. [역할 관리](#13-역할-관리)
14. [GPU 호스트 모니터링](#14-gpu-호스트-모니터링)

---

## 1. 개요 및 리소스 집계

### GET /api/admin/overview

하이퍼바이저, 인스턴스, 컴퓨트/스토리지 리소스 사용량, GPU 인스턴스 수 등 전체 클러스터 개요를 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | `true` 시 캐시 무시하고 새로 조회 |

**응답 (200 OK)**

```json
{
  "hypervisor_count": 5,
  "running_vms": 42,
  "gpu_instances": 3,
  "instance_stats": {
    "total": 42,
    "active": 38,
    "shutoff": 2,
    "error": 1,
    "other": 1
  },
  "vcpus": {
    "total": 160,
    "allowed": 320,
    "used": 85
  },
  "ram_gb": {
    "total": 512.0,
    "used": 256.5
  },
  "disk_gb": {
    "total": 10000,
    "used": 3500
  },
  "containers_count": 0,
  "file_storage_count": 12
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `hypervisor_count` | integer | 하이퍼바이저(호스트) 수 |
| `running_vms` | integer | 실행 중인 VM 총 수 |
| `gpu_instances` | integer | GPU 플레이버를 사용하는 인스턴스 수 |
| `instance_stats` | object | 상태별 인스턴스 집계 |
| `vcpus` | object | vCPU 물리/허용/사용량 |
| `ram_gb` | object | RAM 총/사용량 (GB) |
| `disk_gb` | object | 디스크 총/사용량 (GB) |
| `containers_count` | integer | Zun 컨테이너 수 |
| `file_storage_count` | integer | Manila 파일 스토리지 수 |

### GET /api/admin/hypervisors

컴퓨트 하이퍼바이저 상세 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)** — 배열

```json
[
  {
    "id": "1",
    "name": "compute01",
    "state": "up",
    "status": "enabled",
    "hypervisor_type": "QEMU",
    "vcpus": 32,
    "vcpus_used": 16,
    "memory_size_mb": 131072,
    "memory_used_mb": 65536,
    "local_disk_gb": 500,
    "local_disk_used_gb": 200,
    "running_vms": 8
  }
]
```

### GET /api/admin/overview/projects

프로젝트별 컴퓨트/스토리지 쿼터 및 사용량, GPU 인스턴스 수를 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)** — 배열

```json
[
  {
    "project_id": "uuid-string",
    "project_name": "project-name",
    "cpu": {"used": 8, "quota": 40},
    "ram_mb": {"used": 16384, "quota": 81920},
    "instances": {"used": 5, "quota": 20},
    "disk_gb": {"used": 200, "quota": 1000},
    "gpu_instances": 1
  }
]
```

---

## 2. 파일 스토리지 관리

### GET /api/admin/file-storage

모든 Union 관련 파일 스토리지(Manila share) 목록을 반환합니다. prebuilt + dynamic 모두 포함.

**응답 (200 OK)** — `FileStorageInfo[]` 배열

### POST /api/admin/file-storage/build

사전 빌드(prebuilt) 파일 스토리지 생성을 트리거합니다. 실제 빌드는 별도 백그라운드 프로세스에서 수행됩니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `library_id` | query | string | 예 | 라이브러리 ID (예: `python311`) |

**응답 (202 Accepted)**

```json
{
  "file_storage_id": "uuid-string",
  "status": "building",
  "library": "python311"
}
```

| 오류 | 설명 |
|------|------|
| `404` | 알 수 없는 library_id |
| `409` | 이미 존재하는 사전 빌드 파일 스토리지 |

---

## 3. 인스턴스/볼륨/네트워크 전체 조회

### GET /api/admin/all-instances

전체 프로젝트의 인스턴스 목록을 페이지네이션으로 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `limit` | query | integer | 20 | 페이지 크기 (1~100) |
| `marker` | query | string | - | 이전 페이지 마지막 항목 ID |
| `project_id` | query | string | - | 특정 프로젝트로 필터 |

**응답 (200 OK)**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "vm-name",
      "status": "ACTIVE",
      "project_id": "uuid-string",
      "user_id": "uuid-string",
      "flavor": "m1.small",
      "host": "compute01",
      "created_at": "2024-01-01T00:00:00Z",
      "fault": null
    }
  ],
  "next_marker": "uuid-string-or-null",
  "count": 20
}
```

### GET /api/admin/all-volumes

전체 프로젝트의 볼륨 목록을 페이지네이션으로 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `limit` | query | integer | 20 | 페이지 크기 (1~100) |
| `marker` | query | string | - | 이전 페이지 마지막 항목 ID |

**응답 (200 OK)**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "volume-name",
      "status": "in-use",
      "size": 50,
      "project_id": "uuid-string",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "next_marker": "uuid-string-or-null",
  "count": 20
}
```

### GET /api/admin/all-containers

전체 프로젝트의 Zun 컨테이너 목록을 반환합니다. (Zun 서비스 활성화 시에만 사용 가능)

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

### GET /api/admin/all-file-storages

전체 프로젝트의 Manila 파일 스토리지 목록을 반환합니다. (Manila 서비스 활성화 시에만 사용 가능)

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

### GET /api/admin/all-networks

전체 프로젝트의 네트워크 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

### GET /api/admin/all-floating-ips

전체 프로젝트의 Floating IP 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

### GET /api/admin/all-routers

전체 프로젝트의 라우터 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

### GET /api/admin/all-ports

전체 프로젝트의 포트 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 항목**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 포트 UUID |
| `name` | string | 포트 이름 |
| `status` | string | 상태 |
| `network_id` | string | 네트워크 UUID |
| `device_owner` | string | 디바이스 소유자 |
| `device_id` | string | 디바이스 UUID |
| `mac_address` | string | MAC 주소 |
| `fixed_ips` | array | 고정 IP 목록 |
| `project_id` | string | 프로젝트 UUID |

---

## 4. 토폴로지 및 시계열

### GET /api/admin/topology

전체 프로젝트의 네트워크/라우터/인스턴스 토폴로지를 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)** — `TopologyData`

```json
{
  "networks": [],
  "routers": [],
  "instances": [
    {
      "id": "uuid-string",
      "name": "vm-name",
      "status": "ACTIVE",
      "network_names": ["private-net"],
      "ip_addresses": [
        {"addr": "10.0.0.5", "type": "fixed", "network_name": "private-net"}
      ]
    }
  ]
}
```

### GET /api/admin/timeseries/{resource_type}

리소스 유형별 시계열 스냅샷을 반환합니다. 1시간 간격으로 수집된 데이터입니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `resource_type` | path | string | 예 | `instances`, `volumes`, `file_storage`, `networks` 중 하나 |
| `range` | query | string | `7d` | 조회 범위: `1d`, `2d`, `7d`, `30d` |

**오류 응답**

| 상태 코드 | 설명 |
|-----------|------|
| `400` | 유효하지 않은 resource_type |

---

## 5. 볼륨 관리

### PATCH /api/admin/volumes/{volume_id}

볼륨 이름/설명을 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "description": "string (선택)"
}
```

**응답 (200 OK)**

```json
{
  "id": "uuid-string",
  "name": "new-name",
  "status": "in-use",
  "size": 50
}
```

### DELETE /api/admin/volumes/{volume_id}

볼륨을 삭제합니다.

**응답**: `204 No Content`

### POST /api/admin/volumes/{volume_id}/extend

볼륨 용량을 확장합니다.

**요청 본문**

```json
{
  "new_size": 100
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `new_size` | integer | 예 | 새 크기 (GB). 현재 크기보다 커야 함 |

**응답 (200 OK)**

```json
{
  "status": "extending"
}
```

### POST /api/admin/volumes/{volume_id}/reset-status

볼륨 상태를 강제 초기화합니다. 오류 상태의 볼륨을 복구할 때 사용합니다.

**요청 본문**

```json
{
  "status": "available"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `status` | string | 예 | 설정할 상태 (기본값: `available`) |

---

## 6. 네트워크 관리

### POST /api/admin/networks

네트워크를 생성합니다. 선택적으로 서브넷을 함께 생성할 수 있습니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "is_external": false,
  "is_shared": false,
  "cidr": "192.168.1.0/24 (선택 — 지정하면 서브넷도 함께 생성)",
  "enable_dhcp": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 네트워크 이름 |
| `is_external` | boolean | 아니오 | 외부 네트워크 여부 (기본값: `false`) |
| `is_shared` | boolean | 아니오 | 공유 네트워크 여부 (기본값: `false`) |
| `cidr` | string | 아니오 | 서브넷 CIDR. 지정하면 서브넷도 함께 생성됨 |
| `enable_dhcp` | boolean | 아니오 | DHCP 활성화 여부 (기본값: `true`) |

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "network-name",
  "status": "ACTIVE",
  "is_external": false,
  "is_shared": false,
  "subnets": ["uuid-string"]
}
```

### PUT /api/admin/networks/{network_id}

네트워크를 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "is_shared": true
}
```

### DELETE /api/admin/networks/{network_id}

네트워크를 삭제합니다.

**응답**: `204 No Content`

### POST /api/admin/floating-ips

Floating IP를 생성합니다.

**요청 본문**

```json
{
  "floating_network_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `floating_network_id` | string | 예 | 외부 네트워크 UUID |

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "floating_ip_address": "203.0.113.10",
  "fixed_ip_address": null,
  "status": "ACTIVE",
  "port_id": null,
  "project_id": "uuid-string"
}
```

### DELETE /api/admin/floating-ips/{fip_id}

Floating IP를 삭제합니다.

**응답**: `204 No Content`

### POST /api/admin/routers

라우터를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "external_network_id": "uuid-string (선택)"
}
```

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "router-name",
  "status": "ACTIVE",
  "external_gateway_network_id": "uuid-string",
  "project_id": "uuid-string"
}
```

### PUT /api/admin/routers/{router_id}

라우터를 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "external_network_id": "uuid-string (선택, null이면 게이트웨이 제거)"
}
```

### DELETE /api/admin/routers/{router_id}

라우터를 삭제합니다.

**응답**: `204 No Content`

### PUT /api/admin/ports/{port_id}

포트 이름을 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)"
}
```

### DELETE /api/admin/ports/{port_id}

포트를 삭제합니다.

**응답**: `204 No Content`

---

## 7. 서비스 상태 모니터링

> 태그: `admin-services`

### GET /api/admin/services

Nova, Cinder, Neutron, Manila, Heat, Zun 서비스 상태, API 엔드포인트, 스토리지 풀 정보를 종합적으로 조회합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)**

```json
{
  "compute": [
    {
      "id": "1",
      "binary": "nova-compute",
      "host": "compute01",
      "status": "enabled",
      "state": "up",
      "zone": "nova",
      "updated_at": "2024-01-01T00:00:00Z",
      "disabled_reason": null
    }
  ],
  "block_storage": [],
  "network": [
    {
      "id": "uuid",
      "binary": "neutron-openvswitch-agent",
      "host": "network01",
      "agent_type": "Open vSwitch agent",
      "availability_zone": null,
      "alive": true,
      "admin_state_up": true,
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "shared_file_system": [],
  "orchestration": [],
  "container": [],
  "container_infra": [],
  "endpoints": [
    {
      "service_id": "uuid",
      "name": "nova",
      "service": "compute",
      "region": "RegionOne",
      "endpoints": {
        "public": "http://...",
        "internal": "http://...",
        "admin": "http://..."
      }
    }
  ],
  "storage_pools": [
    {
      "name": "pool-name",
      "volume_backend_name": "ceph",
      "driver_version": "1.0",
      "storage_protocol": "ceph",
      "vendor_name": "Ceph",
      "total_capacity_gb": 10000.0,
      "free_capacity_gb": 6500.0,
      "allocated_capacity_gb": 3500.0
    }
  ]
}
```

---

## 8. Flavor 관리

> 태그: `admin-flavors`

### GET /api/admin/flavors

전체 flavor 목록을 반환합니다 (공개 + 비공개).

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `limit` | query | integer | 20 | 페이지 크기 (1~100) |
| `marker` | query | string | - | 페이지네이션 마커 |
| `is_public` | query | boolean | - | 공개 여부 필터. 생략 시 전체 |

**응답 (200 OK)**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "m1.small",
      "vcpus": 2,
      "ram": 2048,
      "disk": 20,
      "is_public": true,
      "description": "",
      "extra_specs": {},
      "is_gpu": false,
      "gpu_count": 0
    }
  ],
  "next_marker": "uuid-string-or-null",
  "count": 20
}
```

### POST /api/admin/flavors

Flavor를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "vcpus": 4,
  "ram": 8192,
  "disk": 50,
  "is_public": true,
  "description": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | Flavor 이름 |
| `vcpus` | integer | 예 | vCPU 수 |
| `ram` | integer | 예 | RAM (MB) |
| `disk` | integer | 예 | 루트 디스크 (GB) |
| `is_public` | boolean | 아니오 | 공개 여부 (기본값: `true`) |
| `description` | string | 아니오 | 설명 |

**응답 (201 Created)** — 위 목록 응답 항목과 동일

### DELETE /api/admin/flavors/{flavor_id}

Flavor를 삭제합니다.

**응답**: `204 No Content`

### GET /api/admin/flavors/{flavor_id}/access

Flavor 접근 권한이 있는 프로젝트 목록을 반환합니다. 공개 flavor는 빈 배열을 반환합니다.

**응답 (200 OK)**

```json
[
  {
    "flavor_id": "uuid-string",
    "project_id": "uuid-string",
    "project_name": "project-name"
  }
]
```

### POST /api/admin/flavors/{flavor_id}/access

비공개 Flavor에 프로젝트 접근 권한을 추가합니다.

**요청 본문**

```json
{
  "project_id": "uuid-string (필수)"
}
```

### DELETE /api/admin/flavors/{flavor_id}/access/{project_id}

Flavor에서 프로젝트 접근 권한을 제거합니다.

**응답**: `204 No Content`

### POST /api/admin/flavors/{flavor_id}/extra-specs

Flavor에 extra_spec을 추가/수정합니다. GPU 리소스 지정 등에 사용합니다.

**요청 본문**

```json
{
  "key": "string (필수)",
  "value": "string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `key` | string | 예 | extra_spec 키 (예: `resources:VGPU`) |
| `value` | string | 예 | extra_spec 값 (예: `1`) |

**응답 (200 OK)**

```json
{
  "key": "resources:VGPU",
  "value": "1"
}
```

### DELETE /api/admin/flavors/{flavor_id}/extra-specs/{key}

Flavor의 특정 extra_spec을 삭제합니다.

**응답**: `204 No Content`

---

## 9. 사용자 관리

> 태그: `admin-identity`

### GET /api/admin/users

사용자 목록을 페이지네이션으로 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `limit` | query | integer | 20 | 페이지 크기 (1~100) |
| `marker` | query | string | - | 페이지네이션 마커 |

**응답 (200 OK)**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "username",
      "email": "user@example.com",
      "enabled": true,
      "domain_id": "uuid-string",
      "default_project_id": "uuid-string",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "next_marker": "uuid-string-or-null",
  "count": 20
}
```

### POST /api/admin/users

사용자를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "email": "string (선택)",
  "password": "string (선택)",
  "enabled": true,
  "domain_id": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 사용자 이름 |
| `email` | string | 아니오 | 이메일 주소 |
| `password` | string | 아니오 | 초기 비밀번호 |
| `enabled` | boolean | 아니오 | 활성화 여부 (기본값: `true`) |
| `domain_id` | string | 아니오 | 도메인 UUID |

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "username",
  "email": "user@example.com",
  "enabled": true
}
```

### PATCH /api/admin/users/{user_id}

사용자 정보를 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "email": "string (선택)",
  "enabled": true,
  "password": "string (선택)"
}
```

---

## 10. 프로젝트 관리

### GET /api/admin/projects

프로젝트 목록을 페이지네이션으로 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `limit` | query | integer | 20 | 페이지 크기 (1~100) |
| `marker` | query | string | - | 페이지네이션 마커 |

**응답 (200 OK)**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "name": "project-name",
      "description": "설명",
      "enabled": true,
      "domain_id": "uuid-string",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "next_marker": "uuid-string-or-null",
  "count": 20
}
```

### GET /api/admin/projects/names

모든 프로젝트의 id/name 목록을 반환합니다 (페이지네이션 없이 전체).

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)**

```json
[
  {"id": "uuid-string", "name": "project-name"}
]
```

### POST /api/admin/projects

프로젝트를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "description": "string (선택)",
  "domain_id": "string (선택)",
  "enabled": true
}
```

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "project-name",
  "description": "",
  "enabled": true
}
```

### PATCH /api/admin/projects/{project_id}

프로젝트를 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "description": "string (선택)",
  "enabled": true
}
```

### DELETE /api/admin/projects/{project_id}

프로젝트를 삭제합니다.

**응답**: `204 No Content`

### GET /api/admin/projects/{project_id}/members

프로젝트의 사용자-역할 할당 목록을 반환합니다. 그룹 역할 할당도 포함됩니다.

**응답 (200 OK)**

```json
[
  {
    "user_id": "uuid-string",
    "user_name": "username",
    "role_id": "uuid-string",
    "role_name": "member",
    "type": "user"
  },
  {
    "user_id": "group:uuid-string",
    "user_name": "[그룹] group-name",
    "role_id": "uuid-string",
    "role_name": "reader",
    "type": "group",
    "group_id": "uuid-string"
  }
]
```

---

## 11. 쿼터 관리

### GET /api/admin/quotas/{project_id}

프로젝트의 컴퓨트 및 볼륨 쿼터를 조회합니다.

**응답 (200 OK)**

```json
{
  "compute": {
    "instances": {"limit": 20, "in_use": 5},
    "cores": {"limit": 40, "in_use": 10},
    "ram": {"limit": 81920, "in_use": 20480}
  },
  "volume": {
    "volumes": {"limit": 10, "in_use": 3},
    "gigabytes": {"limit": 1000, "in_use": 200}
  }
}
```

### PUT /api/admin/quotas/{project_id}

프로젝트 쿼터를 수정합니다.

**요청 본문**

```json
{
  "instances": 20,
  "cores": 40,
  "ram": 81920,
  "volumes": 10,
  "gigabytes": 1000
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `instances` | integer | 아니오 | 인스턴스 수 한도 |
| `cores` | integer | 아니오 | vCPU 코어 수 한도 |
| `ram` | integer | 아니오 | RAM 한도 (MB) |
| `volumes` | integer | 아니오 | 볼륨 수 한도 |
| `gigabytes` | integer | 아니오 | 볼륨 총 용량 한도 (GB) |

**응답 (200 OK)**

```json
{
  "status": "updated"
}
```

---

## 12. 그룹 관리

### GET /api/admin/groups

그룹 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)**

```json
[
  {
    "id": "uuid-string",
    "name": "group-name",
    "description": "",
    "domain_id": "uuid-string"
  }
]
```

### POST /api/admin/groups

그룹을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "description": "string (선택)",
  "domain_id": "string (선택)"
}
```

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "group-name",
  "description": "",
  "domain_id": "uuid-string"
}
```

### PATCH /api/admin/groups/{group_id}

그룹을 수정합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "description": "string (선택)"
}
```

### DELETE /api/admin/groups/{group_id}

그룹을 삭제합니다.

**응답**: `204 No Content`

### GET /api/admin/groups/{group_id}/users

그룹의 멤버 사용자 목록을 반환합니다.

**응답 (200 OK)**

```json
[
  {
    "id": "uuid-string",
    "name": "username",
    "email": "user@example.com",
    "enabled": true
  }
]
```

### PUT /api/admin/groups/{group_id}/users/{user_id}

그룹에 사용자를 추가합니다.

**응답**: `204 No Content`

### DELETE /api/admin/groups/{group_id}/users/{user_id}

그룹에서 사용자를 제거합니다. 그룹 멤버십 변경 시 Keystone이 토큰을 revoke할 수 있으므로 관련 세션 캐시도 함께 삭제됩니다.

**응답**: `204 No Content`

---

## 13. 역할 관리

### GET /api/admin/roles

역할 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)**

```json
[
  {
    "id": "uuid-string",
    "name": "member",
    "domain_id": null
  }
]
```

### POST /api/admin/roles/assign

사용자에게 프로젝트 역할을 할당합니다.

**요청 본문**

```json
{
  "user_id": "uuid-string (필수)",
  "project_id": "uuid-string (필수)",
  "role_id": "uuid-string (필수)"
}
```

**응답 (200 OK)**

```json
{
  "status": "assigned"
}
```

### DELETE /api/admin/roles/assign

사용자의 프로젝트 역할을 회수합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `user_id` | query | string | 예 | 사용자 UUID |
| `project_id` | query | string | 예 | 프로젝트 UUID |
| `role_id` | query | string | 예 | 역할 UUID |

**응답 (200 OK)**

```json
{
  "status": "revoked"
}
```

### POST /api/admin/roles/assign-group

그룹에 프로젝트 역할을 할당합니다.

**요청 본문**

```json
{
  "group_id": "uuid-string (필수)",
  "project_id": "uuid-string (필수)",
  "role_id": "uuid-string (필수)"
}
```

### DELETE /api/admin/roles/assign-group

그룹의 프로젝트 역할을 회수합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `group_id` | query | string | 예 | 그룹 UUID |
| `project_id` | query | string | 예 | 프로젝트 UUID |
| `role_id` | query | string | 예 | 역할 UUID |

---

## 14. GPU 호스트 모니터링

> 태그: `admin-gpu`

### GET /api/admin/gpu-hosts

Placement API에서 각 호스트별 GPU 정보를 조회합니다. PCI 디바이스 식별, 사용량, 호스트별 집계를 제공합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)**

```json
{
  "hosts": [
    {
      "name": "compute01_0000:03:00.0",
      "uuid": "uuid-string",
      "gpus": [
        {
          "provider_name": "compute01_0000:03:00.0",
          "provider_uuid": "uuid-string",
          "pci_address": "0000:03:00.0",
          "resource_class": "CUSTOM_PCI_10DE_20B0",
          "vendor_id": "10DE",
          "vendor_name": "NVIDIA",
          "device_id": "20B0",
          "device_name": "A100 SXM4 40GB",
          "total": 1,
          "used": 0,
          "allocation_ratio": 1.0,
          "reserved": 0
        }
      ],
      "gpu_total": 1,
      "gpu_used": 0
    }
  ],
  "aggregated_hosts": [
    {
      "name": "compute01",
      "gpus": [],
      "gpu_groups": [
        {
          "device_name": "A100 SXM4 40GB",
          "vendor_name": "NVIDIA",
          "total": 4,
          "used": 2
        }
      ],
      "gpu_total": 4,
      "gpu_used": 2
    }
  ],
  "summary": {
    "total_hosts": 3,
    "total_gpus": 12,
    "used_gpus": 5,
    "available_gpus": 7
  },
  "gpu_types": [
    {
      "device_name": "A100 SXM4 40GB",
      "vendor": "NVIDIA",
      "total": 8,
      "used": 3
    }
  ]
}
```

| 응답 필드 | 설명 |
|-----------|------|
| `hosts` | 개별 리소스 프로바이더(PCI 주소 포함) 단위 GPU 목록 |
| `aggregated_hosts` | 호스트명 기준으로 병합된 GPU 정보 (PCI 주소 접미사 제거) |
| `summary` | 전체 GPU 총/사용/가용 수 |
| `gpu_types` | GPU 모델별 집계 |