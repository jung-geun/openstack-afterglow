# 네트워크 (Networks) API

> 태그: `networks`  
> 기본 경로: `/api/networks`

Neutron 네트워크, 서브넷, Floating IP를 관리합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [네트워크](#1-네트워크)
2. [서브넷](#2-서브넷)
3. [Floating IP](#3-floating-ip)
4. [네트워크 토폴로지](#4-네트워크-토폴로지)

---

## 1. 네트워크

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/networks` | 네트워크 목록 |
| `POST` | `/api/networks` | 네트워크 생성 |
| `GET` | `/api/networks/topology` | 네트워크 토폴로지 전체 (30초 캐시) |
| `GET` | `/api/networks/{network_id}` | 네트워크 상세 (서브넷, 라우터 포함) |
| `DELETE` | `/api/networks/{network_id}` | 네트워크 삭제 |

### GET /api/networks

프로젝트의 Neutron 네트워크 목록을 반환합니다.

**응답 (200 OK)** — `NetworkInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "private-net",
    "status": "ACTIVE",
    "subnets": ["uuid-string"],
    "is_external": false,
    "is_shared": false
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 네트워크 UUID |
| `name` | string | 네트워크 이름 |
| `status` | string | 상태 |
| `subnets` | array[string] | 서브넷 UUID 목록 |
| `is_external` | boolean | 외부 네트워크 여부 |
| `is_shared` | boolean | 공유 네트워크 여부 |

### POST /api/networks

새 네트워크를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 네트워크 이름 |

**응답 (201 Created)** — `NetworkInfo` 객체

### GET /api/networks/topology

프로젝트의 전체 네트워크 토폴로지를 반환합니다. 네트워크, 라우터, 인스턴스, Floating IP 관계를 포함합니다. 응답은 30초간 캐시됩니다.

**응답 (200 OK)** — `TopologyData`

```json
{
  "networks": [],
  "routers": [],
  "instances": [],
  "floating_ips": []
}
```

### GET /api/networks/{network_id}

특정 네트워크의 상세 정보를 반환합니다. 서브넷 상세 정보와 연결된 라우터도 포함합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `network_id` | path | string | 예 | 네트워크 UUID |

**응답 (200 OK)** — `NetworkDetail`

```json
{
  "id": "uuid-string",
  "name": "private-net",
  "status": "ACTIVE",
  "subnets": ["uuid-string"],
  "is_external": false,
  "is_shared": false,
  "subnet_details": [
    {
      "id": "uuid-string",
      "name": "subnet-name",
      "cidr": "192.168.1.0/24",
      "gateway_ip": "192.168.1.1",
      "dhcp_enabled": true
    }
  ],
  "routers": [
    {
      "id": "uuid-string",
      "name": "router-name",
      "status": "ACTIVE",
      "project_id": "uuid-string",
      "external_gateway_network_id": "uuid-string",
      "connected_subnet_ids": ["uuid-string"]
    }
  ]
}
```

### DELETE /api/networks/{network_id}

네트워크를 삭제합니다. 서브넷이나 연결된 포트가 있으면 삭제할 수 없습니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `network_id` | path | string | 예 | 네트워크 UUID |

**응답**: `204 No Content`

---

## 2. 서브넷

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/networks/{network_id}/subnets` | 서브넷 생성 |
| `DELETE` | `/api/networks/subnets/{subnet_id}` | 서브넷 삭제 |

### POST /api/networks/{network_id}/subnets

지정한 네트워크에 서브넷을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "cidr": "192.168.1.0/24 (필수)",
  "gateway_ip": "string (선택)",
  "enable_dhcp": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 서브넷 이름 |
| `cidr` | string | 예 | CIDR 표기법 (예: `192.168.1.0/24`) |
| `gateway_ip` | string | 아니오 | 게이트웨이 IP. 생략 시 CIDR의 첫 번째 IP 사용 |
| `enable_dhcp` | boolean | 아니오 | DHCP 활성화 여부 (기본값: `true`) |

### DELETE /api/networks/subnets/{subnet_id}

서브넷을 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `subnet_id` | path | string | 예 | 서브넷 UUID |

**응답**: `204 No Content`

---

## 3. Floating IP

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/networks/floating-ips` | Floating IP 목록 |
| `POST` | `/api/networks/floating-ips` | Floating IP 생성 |
| `POST` | `/api/networks/floating-ips/{fip_id}/associate` | Floating IP 인스턴스 연결 |
| `POST` | `/api/networks/floating-ips/{fip_id}/disassociate` | Floating IP 해제 |
| `DELETE` | `/api/networks/floating-ips/{fip_id}` | Floating IP 삭제 |

### GET /api/networks/floating-ips

프로젝트의 Floating IP 목록을 반환합니다.

**응답 (200 OK)** — `FloatingIpInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "floating_ip_address": "203.0.113.10",
    "fixed_ip_address": "10.0.0.5",
    "status": "ACTIVE",
    "port_id": "uuid-string",
    "floating_network_id": "uuid-string",
    "project_id": "uuid-string"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | Floating IP UUID |
| `floating_ip_address` | string | Floating IP 주소 |
| `fixed_ip_address` | string\|null | 연결된 고정 IP 주소 |
| `status` | string | 상태 (`ACTIVE`, `DOWN` 등) |
| `port_id` | string\|null | 연결된 포트 UUID |
| `floating_network_id` | string | 외부 네트워크 UUID |
| `project_id` | string\|null | 프로젝트 UUID |

### POST /api/networks/floating-ips

새 Floating IP를 외부 네트워크에서 할당받습니다.

**요청 본문**

```json
{
  "floating_network_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `floating_network_id` | string | 예 | 외부 네트워크 UUID |

**응답 (201 Created)** — `FloatingIpInfo` 객체

### POST /api/networks/floating-ips/{fip_id}/associate

Floating IP를 인스턴스에 연결합니다.

**요청 본문**

```json
{
  "instance_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `instance_id` | string | 예 | 연결할 인스턴스 UUID |

### POST /api/networks/floating-ips/{fip_id}/disassociate

Floating IP를 인스턴스에서 해제합니다. Floating IP 자체는 유지됩니다.

### DELETE /api/networks/floating-ips/{fip_id}

Floating IP를 삭제(반환)합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `fip_id` | path | string | 예 | Floating IP UUID |

**응답**: `204 No Content`

---

## 4. 네트워크 토폴로지

### GET /api/networks/topology

프로젝트의 전체 네트워크 토폴로지를 반환합니다. 응답은 30초간 캐시됩니다.

> 위의 **네트워크 토폴로지** 섹션과 동일한 엔드포인트입니다.