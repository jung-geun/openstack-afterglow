# 인증 (Auth) API

> 태그: `auth`  
> 기본 경로: `/api/auth`

Keystone 인증 토큰 발급, 세션 관리, 프로젝트 조회를 제공합니다.

---

## 인증 헤더

인증이 필요한 엔드포인트(로그인 제외)에는 다음 헤더를 포함해야 합니다.

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 엔드포인트 목록

| 메서드 | 경로 | 인증 필요 | 설명 |
|--------|------|-----------|------|
| `POST` | `/api/auth/login` | 없음 | 사용자 이름/비밀번호로 Keystone 토큰 발급 |
| `GET` | `/api/auth/me` | 필요 | 현재 토큰의 사용자/프로젝트 정보 반환 |
| `GET` | `/api/auth/projects` | 필요 | 사용자가 접근 가능한 프로젝트 목록 반환 |
| `POST` | `/api/auth/token` | 필요 | 다른 프로젝트로 스코프 전환 (새 토큰 발급) |

---

## POST /api/auth/login

Keystone에 사용자 자격증명으로 인증하여 토큰을 발급받습니다. 로그인 성공 시 Redis에 세션 시작 시간을 저장합니다.

### 요청 본문

```json
{
  "username": "string (필수)",
  "password": "string (필수)",
  "project_name": "string (선택)",
  "domain_name": "string (선택, 기본값: Default)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `username` | string | 예 | OpenStack 사용자 이름 |
| `password` | string | 예 | OpenStack 비밀번호 |
| `project_name` | string | 아니오 | 스코프할 프로젝트 이름. 생략 시 사용자 기본 프로젝트 사용 |
| `domain_name` | string | 아니오 | 사용자 도메인 이름 (기본값: `Default`) |

### 응답 (200 OK)

```json
{
  "token": "gAAAAA...",
  "project_id": "uuid-string",
  "project_name": "project-name",
  "user_id": "uuid-string",
  "username": "user-name",
  "expires_at": "2024-01-01T00:00:00Z"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `token` | string | Keystone 인증 토큰. 이후 API 요청의 `X-Auth-Token` 헤더에 사용 |
| `project_id` | string | 스코프된 프로젝트 UUID |
| `project_name` | string | 프로젝트 이름 |
| `user_id` | string | 사용자 UUID |
| `username` | string | 사용자 이름 |
| `expires_at` | string | 토큰 만료 시간 (ISO 8601) |

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 잘못된 사용자 이름 또는 비밀번호 |
| `400` | 요청 본문 형식 오류 |

---

## GET /api/auth/me

현재 `X-Auth-Token`에 해당하는 사용자와 프로젝트 정보를 반환합니다.

### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Auth-Token` | 예 | 유효한 Keystone 토큰 |
| `X-Project-Id` | 예 | 프로젝트 UUID |

### 응답 (200 OK)

```json
{
  "user_id": "uuid-string",
  "username": "user-name",
  "project_id": "uuid-string",
  "project_name": "project-name",
  "roles": ["member", "reader"]
}
```

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |

---

## GET /api/auth/projects

현재 사용자가 접근 가능한 모든 OpenStack 프로젝트 목록을 반환합니다. 프로젝트 전환 시 사용합니다.

### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Auth-Token` | 예 | 유효한 Keystone 토큰 |
| `X-Project-Id` | 예 | 프로젝트 UUID |

### 응답 (200 OK)

```json
[
  {
    "id": "uuid-string",
    "name": "project-name",
    "description": "프로젝트 설명",
    "enabled": true,
    "domain_id": "uuid-string"
  }
]
```

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |

---

## POST /api/auth/token

현재 토큰을 기반으로 다른 프로젝트로 스코프된 새 토큰을 발급합니다. 프로젝트 전환 시 사용합니다.

### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Auth-Token` | 예 | 유효한 Keystone 토큰 |
| `X-Project-Id` | 예 | 현재 프로젝트 UUID |

### 요청 본문

```json
{
  "project_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `project_id` | string | 예 | 스코프할 대상 프로젝트 UUID |

### 응답 (200 OK)

```json
{
  "token": "gAAAAA...",
  "project_id": "uuid-string",
  "project_name": "project-name",
  "user_id": "uuid-string",
  "username": "user-name",
  "expires_at": "2024-01-01T00:00:00Z"
}
```

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |
| `403` | 대상 프로젝트 접근 권한 없음 |