# 라우터 (Routers) API

> 태그: `routers`  
> 기본 경로: `/api/routers`

Neutron 라우터와 인터페이스, 게이트웨이를 관리합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/routers` | 라우터 목록 (30초 캐시) |
| `POST` | `/api/routers` | 라우터 생성 |
| `GET` | `/api/routers/{router_id}` | 라우터 상세 (인터페이스 포함) |
| `DELETE` | `/api/routers/{router_id}` | 라우터 삭제 |
| `POST` | `/api/routers/{router_id}/interfaces` | 서브넷 인터페이스 추가 |
| `DELETE` | `/api/routers/{router_id}/interfaces/{subnet_id}` | 인터페이스 제거 |
| `POST` | `/api/routers/{router_id}/gateway` | 외부 게이트웨이 설정 |
| `DELETE` | `/api/routers/{router_id}/gateway` | 게이트웨이 제거 |

---

## GET /api/routers

프로젝트의 Neutron 라우터 목록을 반환합니다. 응답은 30초간 캐시됩니다.

**응답 (200 OK)** — `RouterInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "router-name",
    "status": "ACTIVE",
    "project_id": "uuid-string",
    "external_gateway_network_id": "uuid-string",
    "connected_subnet_ids": ["uuid-string"]
  }
]
```

---

## POST /api/routers

새 라우터를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "external_network_id": "uuid-string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 라우터 이름 |
| `external_network_id` | string | 아니오 | 외부 게이트웨이로 설정할 네트워크 UUID |

**응답 (201 Created)** — `RouterInfo` 객체

---

## GET /api/routers/{router_id}

특정 라우터의 상세 정보를 반환합니다. 연결된 인터페이스 목록을 포함합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `router_id` | path | string | 예 | 라우터 UUID |

**응답 (200 OK)** — `RouterDetail`

```json
{
  "id": "uuid-string",
  "name": "router-name",
  "status": "ACTIVE",
  "project_id": "uuid-string",
  "external_gateway_network_id": "uuid-string",
  "external_gateway_network_name": "external-net",
  "interfaces": [
    {
      "id": "uuid-string (포트 ID)",
      "subnet_id": "uuid-string",
      "subnet_name": "subnet-name",
      "network_id": "uuid-string",
      "ip_address": "192.168.1.1"
    }
  ]
}
```

---

## DELETE /api/routers/{router_id}

라우터를 삭제합니다. 연결된 인터페이스가 있으면 먼저 제거해야 합니다.

**응답**: `204 No Content`

---

## POST /api/routers/{router_id}/interfaces

라우터에 서브넷 인터페이스를 추가합니다.

**요청 본문**

```json
{
  "subnet_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `subnet_id` | string | 예 | 연결할 서브넷 UUID |

---

## DELETE /api/routers/{router_id}/interfaces/{subnet_id}

라우터에서 서브넷 인터페이스를 제거합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `router_id` | path | string | 예 | 라우터 UUID |
| `subnet_id` | path | string | 예 | 서브넷 UUID |

**응답**: `204 No Content`

---

## POST /api/routers/{router_id}/gateway

라우터에 외부 게이트웨이를 설정합니다.

**요청 본문**

```json
{
  "external_network_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `external_network_id` | string | 예 | 외부 네트워크 UUID |

---

## DELETE /api/routers/{router_id}/gateway

라우터의 외부 게이트웨이를 제거합니다.

**응답**: `204 No Content`