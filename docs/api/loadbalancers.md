# 로드밸런서 (Load Balancers) API

> 태그: `loadbalancers`  
> 기본 경로: `/api/loadbalancers`

Octavia 로드밸런서와 리스너, 풀, 멤버, 헬스 모니터를 관리합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [로드밸런서](#1-로드밸런서)
2. [리스너](#2-리스너)
3. [풀](#3-풀)
4. [멤버](#4-멤버)
5. [헬스 모니터](#5-헬스-모니터)

---

## 1. 로드밸런서

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers` | 로드밸런서 목록 (30초 캐시) |
| `POST` | `/api/loadbalancers` | 로드밸런서 생성 |
| `GET` | `/api/loadbalancers/{lb_id}` | 로드밸런서 상세 |
| `DELETE` | `/api/loadbalancers/{lb_id}` | 로드밸런서 삭제 |

### GET /api/loadbalancers

프로젝트의 Octavia 로드밸런서 목록을 반환합니다. 응답은 30초간 캐시됩니다.

**응답 (200 OK)** — 배열

### POST /api/loadbalancers

새 로드밸런서를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "vip_subnet_id": "uuid-string (필수)",
  "description": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 로드밸런서 이름 |
| `vip_subnet_id` | string | 예 | VIP가 할당될 서브넷 UUID |
| `description` | string | 아니오 | 설명 |

**응답 (201 Created)**

### GET /api/loadbalancers/{lb_id}

특정 로드밸런서의 상세 정보를 반환합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `lb_id` | path | string | 예 | 로드밸런서 UUID |

### DELETE /api/loadbalancers/{lb_id}

로드밸런서를 삭제합니다. 하위 리스너, 풀도 함께 삭제됩니다.

**응답**: `204 No Content`

---

## 2. 리스너

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/listeners` | 리스너 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/listeners` | 리스너 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/listeners/{listener_id}` | 리스너 삭제 |

### GET /api/loadbalancers/{lb_id}/listeners

로드밸런서의 리스너 목록을 반환합니다.

### POST /api/loadbalancers/{lb_id}/listeners

리스너를 생성합니다.

**요청 본문**

```json
{
  "protocol": "HTTP",
  "protocol_port": 80,
  "name": "string (선택)",
  "default_pool_id": "uuid-string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `protocol` | string | 예 | 프로토콜 (`HTTP`, `HTTPS`, `TCP`, `UDP` 등) |
| `protocol_port` | integer | 예 | 포트 번호 |
| `name` | string | 아니오 | 리스너 이름 |
| `default_pool_id` | string | 아니오 | 기본 풀 UUID |

### DELETE /api/loadbalancers/{lb_id}/listeners/{listener_id}

리스너를 삭제합니다.

**응답**: `204 No Content`

---

## 3. 풀

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools` | 풀 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/pools` | 풀 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}` | 풀 삭제 |

### GET /api/loadbalancers/{lb_id}/pools

로드밸런서의 풀 목록을 반환합니다.

### POST /api/loadbalancers/{lb_id}/pools

풀을 생성합니다.

**요청 본문**

```json
{
  "protocol": "HTTP",
  "lb_algorithm": "ROUND_ROBIN",
  "name": "string (선택)",
  "listener_id": "uuid-string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `protocol` | string | 예 | 프로토콜 (`HTTP`, `HTTPS`, `TCP`, `UDP` 등) |
| `lb_algorithm` | string | 예 | 로드밸런싱 알고리즘 (`ROUND_ROBIN`, `LEAST_CONNECTIONS`, `SOURCE_IP` 등) |
| `name` | string | 아니오 | 풀 이름 |
| `listener_id` | string | 아니오 | 연결할 리스너 UUID |

### DELETE /api/loadbalancers/{lb_id}/pools/{pool_id}

풀을 삭제합니다.

**응답**: `204 No Content`

---

## 4. 멤버

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members` | 멤버 목록 |
| `POST` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members` | 멤버 추가 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/members/{member_id}` | 멤버 제거 |

### GET /api/loadbalancers/{lb_id}/pools/{pool_id}/members

풀의 멤버 목록을 반환합니다.

### POST /api/loadbalancers/{lb_id}/pools/{pool_id}/members

풀에 멤버를 추가합니다.

**요청 본문**

```json
{
  "address": "192.168.1.10 (필수)",
  "protocol_port": 8080,
  "subnet_id": "uuid-string (선택)",
  "name": "string (선택)",
  "weight": 1
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `address` | string | 예 | 멤버 IP 주소 |
| `protocol_port` | integer | 예 | 포트 번호 |
| `subnet_id` | string | 아니오 | 멤버가 속한 서브넷 UUID |
| `name` | string | 아니오 | 멤버 이름 |
| `weight` | integer | 아니오 | 가중치 (기본값: `1`) |

### DELETE /api/loadbalancers/{lb_id}/pools/{pool_id}/members/{member_id}

멤버를 제거합니다.

**응답**: `204 No Content`

---

## 5. 헬스 모니터

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor` | 헬스 모니터 조회 |
| `POST` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor` | 헬스 모니터 생성 |
| `DELETE` | `/api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor/{hm_id}` | 헬스 모니터 삭제 |

### GET /api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor

풀의 헬스 모니터 정보를 반환합니다.

### POST /api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor

헬스 모니터를 생성합니다.

**요청 본문**

```json
{
  "type": "HTTP",
  "delay": 5,
  "timeout": 5,
  "max_retries": 3,
  "name": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string | 예 | 헬스 체크 타입 (`HTTP`, `HTTPS`, `TCP`, `PING` 등) |
| `delay` | integer | 예 | 체크 간격 (초) |
| `timeout` | integer | 예 | 타임아웃 (초) |
| `max_retries` | integer | 예 | 최대 재시도 횟수 |
| `name` | string | 아니오 | 헬스 모니터 이름 |

### DELETE /api/loadbalancers/{lb_id}/pools/{pool_id}/health-monitor/{hm_id}

헬스 모니터를 삭제합니다.

**응답**: `204 No Content`