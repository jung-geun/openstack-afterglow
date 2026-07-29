---
title: 키 관리 (Barbican)
parent: API 레퍼런스
nav_order: 60
---

# 키 관리 (Barbican) API

Barbican 기반 시크릿(비밀 값)·시크릿 컨테이너·주문(order)을 관리합니다. 임의의 페이로드(인증서, 개인키, 대칭키, 비밀번호 등)를 안전하게 저장하고, 프로젝트 내 다른 사용자에게 ACL로 접근을 위임하며, 서버 측 키 생성을 주문할 수 있습니다.

> **선택 서비스** — `afterglow.conf [services]` 에서 활성화해야 사용할 수 있습니다.
> 비활성화 상태에서 이 엔드포인트에 접근하면 라우터 미등록(404)이 반환됩니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <access_token>` (로그인 응답의 access JWT) |
| `X-Project-Id` | (선택) 프로젝트 UUID — 생략 시 토큰의 프로젝트로 처리, 다른 값이면 rescope |

모든 조회는 project-scoped 연결(`get_os_conn`)로 이루어지므로 Keystone이 테넌트 격리를 보장합니다. 생성·삭제 등 변경(mutation) 엔드포인트는 추가로 사용자 JWT(`get_token_info`)를 요구하고 활동 로그(activity audit)를 남깁니다.

---

## 목차

1. [시크릿 (Secrets)](#1-시크릿-secrets)
2. [ACL (접근 위임)](#2-acl-접근-위임)
3. [시크릿 컨테이너 (Containers)](#3-시크릿-컨테이너-containers)
4. [주문 (Orders)](#4-주문-orders)
5. [프로젝트 쿼터](#5-프로젝트-쿼터)

---

## 1. 시크릿 (Secrets)

기본 경로: `/api/v1/secrets`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/secrets` | 시크릿 목록 (캐시) |
| `POST` | `/api/v1/secrets` | 시크릿 생성 (201, 20/분) |
| `GET` | `/api/v1/secrets/{secret_id}/meta` | 시크릿 메타데이터 |
| `GET` | `/api/v1/secrets/{secret_id}/payload` | **페이로드(평문) 다운로드** |
| `DELETE` | `/api/v1/secrets/{secret_id}` | 시크릿 삭제 (204, 20/분) |

### POST /api/v1/secrets

새 시크릿을 생성합니다. `payload` 를 함께 전달하면 즉시 저장되고, 생략하면 메타데이터만 등록된 뒤 별도로 페이로드를 채울 수 있습니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "secret_type": "opaque",
  "payload": "string (선택)",
  "payload_content_type": "text/plain",
  "algorithm": "string (선택)",
  "bit_length": 256,
  "mode": "string (선택)",
  "expiration": "ISO8601 (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 시크릿 이름 |
| `secret_type` | string | 아니오 | 시크릿 타입 (기본값: `opaque`) |
| `payload` | string | 아니오 | 저장할 평문 값 |
| `payload_content_type` | string | 아니오 | 페이로드 MIME 타입 (기본값: `text/plain`) |
| `algorithm` | string | 아니오 | 알고리즘 (예: `aes`) |
| `bit_length` | integer | 아니오 | 키 비트 길이 |
| `mode` | string | 아니오 | 암호 모드 (예: `cbc`) |
| `expiration` | string | 아니오 | 만료 시각 (ISO8601) |

**응답 (201 Created)** — `SecretInfo`

### GET /api/v1/secrets/{secret_id}/meta

시크릿의 메타데이터만 반환합니다(페이로드 제외). 존재하지 않으면 `404`.

### GET /api/v1/secrets/{secret_id}/payload

시크릿의 **복호화된 평문 페이로드**를 `application/octet-stream` 으로 반환합니다.

- 이 응답은 **캐시하지 않으며 로그에 남기지 않습니다** (평문 비밀 값 노출 방지).
- 페이로드 조회는 별도 엔드포인트로 분리되어 있어, 목록/메타 조회에서는 평문이 절대 노출되지 않습니다.
- 조회 실패 시 존재 여부를 구분하지 않고 `404` 를 반환합니다.

### DELETE /api/v1/secrets/{secret_id}

시크릿을 삭제합니다. **시스템 관리(system-managed) 시크릿**을 삭제하려 하면 `403` 이 반환됩니다.

**응답**: `204 No Content`

---

## 2. ACL (접근 위임)

시크릿·컨테이너는 프로젝트 내 특정 사용자에게 접근을 위임할 수 있습니다. Barbican ACL은 소유 프로젝트 외 사용자를 명시적으로 허용하거나, `project_access` 를 꺼서 소유자 전용으로 잠글 수 있습니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/secrets/{secret_id}/acl` | 시크릿 ACL 조회 |
| `PUT` | `/api/v1/secrets/{secret_id}/acl` | 시크릿 ACL 설정 (20/분) |
| `DELETE` | `/api/v1/secrets/{secret_id}/acl` | 시크릿 ACL 초기화 (204, 20/분) |
| `GET` | `/api/v1/secrets/{secret_id}/consumers` | 시크릿 consumer 목록 |

### PUT /api/v1/secrets/{secret_id}/acl

시크릿의 ACL을 설정합니다(전체 교체).

**요청 본문**

```json
{
  "users": ["keystone-user-id", "..."],
  "project_access": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `users` | string[] | 아니오 | 접근을 허용할 Keystone 사용자 ID 목록 (기본값: `[]`) |
| `project_access` | boolean | 아니오 | 소유 프로젝트 전체 접근 허용 여부 (기본값: `true`, `false` 로 두면 `users` 만 접근 가능) |

### DELETE /api/v1/secrets/{secret_id}/acl

ACL을 초기화합니다(기본 프로젝트 접근으로 복원).

**응답**: `204 No Content`

### GET /api/v1/secrets/{secret_id}/consumers

이 시크릿을 참조(consume)하는 리소스 목록을 반환합니다.

---

## 3. 시크릿 컨테이너 (Containers)

기본 경로: `/api/v1/secret-containers`

컨테이너는 여러 시크릿을 하나의 논리적 단위(예: TLS 인증서 + 개인키 + 중간 인증서)로 묶습니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/secret-containers` | 컨테이너 목록 (캐시) |
| `POST` | `/api/v1/secret-containers` | 컨테이너 생성 (201, 20/분) |
| `DELETE` | `/api/v1/secret-containers/{container_id}` | 컨테이너 삭제 (204, 20/분) |
| `GET` | `/api/v1/secret-containers/{container_id}/acl` | 컨테이너 ACL 조회 |
| `PUT` | `/api/v1/secret-containers/{container_id}/acl` | 컨테이너 ACL 설정 (20/분) |
| `GET` | `/api/v1/secret-containers/{container_id}/consumers` | 컨테이너 consumer 목록 |

### POST /api/v1/secret-containers

**요청 본문**

```json
{
  "name": "string (필수)",
  "container_type": "generic",
  "secret_refs": [
    { "name": "private_key", "secret_ref": "https://.../secrets/{id}" }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 컨테이너 이름 |
| `container_type` | string | 아니오 | 컨테이너 타입 (`generic`, `rsa`, `certificate`; 기본값: `generic`) |
| `secret_refs` | object[] | 아니오 | 묶을 시크릿 참조 목록 (`name` + `secret_ref`) |

**응답 (201 Created)** — `ContainerInfo`

ACL(`GET`/`PUT`)과 consumers 는 시크릿과 동일한 모델을 따릅니다([2. ACL](#2-acl-접근-위임) 참조).

---

## 4. 주문 (Orders)

기본 경로: `/api/v1/secret-orders`

주문은 서버 측(Barbican)에서 시크릿을 **생성**하도록 요청하는 비동기 작업입니다(예: 대칭키 생성, 비대칭 키쌍 생성, 인증서 발급). 완료되면 결과 시크릿/컨테이너 참조가 채워집니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/secret-orders` | 주문 목록 (캐시) |
| `POST` | `/api/v1/secret-orders` | 주문 생성 (201, 10/분) |
| `GET` | `/api/v1/secret-orders/{order_id}` | 주문 상세 (진행 상태 확인) |
| `DELETE` | `/api/v1/secret-orders/{order_id}` | 주문 삭제 (204, 10/분) |

### POST /api/v1/secret-orders

**요청 본문**

```json
{
  "order_type": "key",
  "meta": {
    "name": "my-generated-key",
    "algorithm": "aes",
    "bit_length": 256,
    "mode": "cbc"
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `order_type` | string | 예 | 주문 유형 (`key`, `asymmetric`, `certificate`) |
| `meta` | object | 예 | 생성할 시크릿의 파라미터 (알고리즘·비트 길이·이름 등) |

**응답 (201 Created)** — `OrderInfo` (`status`, `secret_ref`, `container_ref`, `error_reason` 포함)

### GET /api/v1/secret-orders/{order_id}

주문 진행 상태를 조회합니다. 완료되면 `secret_ref` 또는 `container_ref` 가 채워집니다. 존재하지 않으면 `404`.

---

## 5. 프로젝트 쿼터

### GET /api/v1/secrets/quota/effective

현재 프로젝트에 **실효 적용되는** Barbican 쿼터를 반환합니다. 관리자가 별도 지정한 값이 없으면 시스템 기본 쿼터가 적용됩니다.

**응답 (200 OK)** — 항목: `secrets`, `orders`, `containers`, `consumers`, `cas` (각 `-1` 은 무제한)

> **쿼터 설정(관리자 전용)** 은 이 문서 범위 밖입니다. 시스템 관리자는 `/api/v1/admin/key-manager/...` 경로로 프로젝트별 쿼터를 조회·설정합니다. 여기의 `quota/effective` 는 일반 사용자가 자신에게 적용된 한도를 확인하는 읽기 전용 엔드포인트입니다.
