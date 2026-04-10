# 프로필 (Profile) API

> 태그: `profile`  
> 기본 경로: `/api/profile`

현재 로그인한 사용자의 프로필 정보를 관리합니다.

---

## 인증 헤더

모든 엔드포인트에 인증 헤더가 필요합니다.

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/profile` | 현재 사용자 프로필 정보 반환 |
| `PUT` | `/api/profile/password` | 비밀번호 변경 |

---

## GET /api/profile

현재 인증된 사용자의 상세 프로필 정보를 반환합니다.

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
  "email": "user@example.com",
  "domain_id": "uuid-string",
  "domain_name": "Default",
  "default_project_id": "uuid-string",
  "enabled": true,
  "roles": ["member", "reader"]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `user_id` | string | 사용자 UUID |
| `username` | string | 사용자 이름 |
| `email` | string\|null | 이메일 주소 |
| `domain_id` | string | 사용자 도메인 UUID |
| `domain_name` | string | 도메인 이름 |
| `default_project_id` | string\|null | 기본 프로젝트 UUID |
| `enabled` | boolean | 계정 활성화 여부 |
| `roles` | array[string] | 현재 프로젝트에서의 역할 목록 |

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |

---

## PUT /api/profile/password

현재 사용자의 비밀번호를 변경합니다. Keystone 비밀번호 변경 API를 호출합니다.

### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `X-Auth-Token` | 예 | 유효한 Keystone 토큰 |
| `X-Project-Id` | 예 | 프로젝트 UUID |

### 요청 본문

```json
{
  "current_password": "string (필수)",
  "new_password": "string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `current_password` | string | 예 | 현재 비밀번호 |
| `new_password` | string | 예 | 새 비밀번호 |

### 응답 (200 OK)

```json
{
  "message": "비밀번호가 변경되었습니다."
}
```

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 현재 비밀번호가 일치하지 않거나 토큰이 만료됨 |
| `400` | 새 비밀번호가 정책 요구사항을 충족하지 않음 |