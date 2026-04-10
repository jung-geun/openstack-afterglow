# 보안 그룹 (Security Groups) API

> 태그: `security-groups`  
> 기본 경로: `/api/security-groups`

Neutron 보안 그룹과 규칙을 관리합니다. 인스턴스의 네트워크 트래픽 접근 제어에 사용됩니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [보안 그룹](#1-보안-그룹)
2. [보안 그룹 규칙](#2-보안-그룹-규칙)

---

## 1. 보안 그룹

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/security-groups` | 보안 그룹 목록 (60초 캐시) |
| `POST` | `/api/security-groups` | 보안 그룹 생성 |
| `DELETE` | `/api/security-groups/{sg_id}` | 보안 그룹 삭제 |

### GET /api/security-groups

프로젝트의 보안 그룹 목록을 반환합니다. 응답은 60초간 캐시됩니다.

**응답 (200 OK)** — 배열

```json
[
  {
    "id": "uuid-string",
    "name": "default",
    "description": "Default security group",
    "rules": [
      {
        "id": "uuid-string",
        "direction": "ingress",
        "protocol": null,
        "port_range_min": null,
        "port_range_max": null,
        "remote_ip_prefix": null,
        "ethertype": "IPv4"
      }
    ]
  }
]
```

### POST /api/security-groups

새 보안 그룹을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "description": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 보안 그룹 이름 |
| `description` | string | 아니오 | 설명 |

**응답 (201 Created)**

### DELETE /api/security-groups/{sg_id}

보안 그룹을 삭제합니다. 기본 보안 그룹은 삭제할 수 없습니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `sg_id` | path | string | 예 | 보안 그룹 UUID |

**응답**: `204 No Content`

---

## 2. 보안 그룹 규칙

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/security-groups/{sg_id}/rules` | 보안 그룹 규칙 추가 |
| `DELETE` | `/api/security-groups/{sg_id}/rules/{rule_id}` | 보안 그룹 규칙 삭제 |

### POST /api/security-groups/{sg_id}/rules

보안 그룹에 새 규칙을 추가합니다.

**요청 본문**

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

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `direction` | string | 예 | 트래픽 방향 (`ingress`, `egress`) |
| `protocol` | string | 아니오 | 프로토콜 (`tcp`, `udp`, `icmp`, `null` = 모든 프로토콜) |
| `port_range_min` | integer | 아니오 | 최소 포트 번호 |
| `port_range_max` | integer | 아니오 | 최대 포트 번호 |
| `remote_ip_prefix` | string | 아니오 | 원격 IP 대역 (CIDR 표기법, 예: `0.0.0.0/0`) |
| `ethertype` | string | 아니오 | 이더타입 (`IPv4`, `IPv6`, 기본값: `IPv4`) |

| direction 허용 값 | 설명 |
|-------------------|------|
| `ingress` | 인바운드 트래픽 (수신) |
| `egress` | 아웃바운드 트래픽 (송신) |

| protocol 허용 값 | 설명 |
|-----------------|------|
| `tcp` | TCP |
| `udp` | UDP |
| `icmp` | ICMP |
| `null` | 모든 프로토콜 |

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "direction": "ingress",
  "protocol": "tcp",
  "port_range_min": 22,
  "port_range_max": 22,
  "remote_ip_prefix": "0.0.0.0/0",
  "ethertype": "IPv4",
  "security_group_id": "uuid-string"
}
```

### DELETE /api/security-groups/{sg_id}/rules/{rule_id}

보안 그룹 규칙을 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `sg_id` | path | string | 예 | 보안 그룹 UUID |
| `rule_id` | path | string | 예 | 규칙 UUID |

**응답**: `204 No Content`