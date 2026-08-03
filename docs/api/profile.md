---
title: 프로필 (Profile)
parent: API 레퍼런스
nav_order: 11
---

# 프로필 (Profile) API

> 태그: `profile`
> 기본 경로: `/api/v1/profile`

현재 로그인한 사용자 본인의 프로필 조회·수정, 비밀번호 변경, 활동 로그 조회를 제공합니다.
모든 엔드포인트는 [인증](auth.html)이 필요합니다.

---

## 인증 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `Authorization` | 예 | `Bearer <access_jwt>` |
| `X-Project-Id` | 아니오 | 처리 대상 프로젝트 UUID |

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/profile` | 본인 프로필 조회 |
| `PATCH` | `/api/v1/profile` | 본인 프로필 수정 (이름·이메일·설명·기본 프로젝트) |
| `POST` | `/api/v1/profile/password` | 비밀번호 변경 (5회/분) |
| `GET` | `/api/v1/profile/activity` | 본인 활동 로그 조회 (cross-project) |

---

## GET /api/v1/profile

현재 인증된 사용자의 상세 프로필을 반환합니다.

### 응답 (200 OK)

```json
{
  "id": "uuid-string",
  "name": "user-name",
  "email": "user@example.com",
  "description": "",
  "default_project_id": "uuid-string"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 사용자 UUID |
| `name` | string | 사용자 이름 |
| `email` | string | 이메일 주소 (없으면 `""`) |
| `description` | string | 설명 (없으면 `""`) |
| `default_project_id` | string | 기본 프로젝트 UUID (없으면 `""`) |

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |
| `500` | 프로필 조회 실패 |

---

## PATCH /api/v1/profile

본인 프로필을 수정합니다. 전달한 필드만 갱신되며, 하나도 없으면 400을 반환합니다.

### 요청 본문

```json
{
  "name": "string (선택)",
  "email": "string (선택)",
  "description": "string (선택)",
  "default_project_id": "uuid-string (선택)"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string\|null | 사용자 이름 |
| `email` | string\|null | 이메일 주소 |
| `description` | string\|null | 설명 |
| `default_project_id` | string\|null | 기본 프로젝트 UUID |

### 응답 (200 OK)

`GET /api/v1/profile`과 동일한 프로필 객체를 반환합니다.

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `400` | 수정할 항목이 없거나 프로필 수정 실패 |
| `401` | 유효하지 않거나 만료된 토큰 |

---

## POST /api/v1/profile/password

현재 비밀번호를 검증한 뒤 새 비밀번호로 변경합니다. Keystone 비밀번호 변경 API를
호출합니다. 비율 제한: **5회/분**.

> 외부(federated) 로그인 사용자는 로컬 비밀번호가 없으므로 변경할 수 없습니다(403).

### 요청 본문

```json
{
  "current_password": "string (필수)",
  "new_password": "string (필수)"
}
```

### 응답 (200 OK)

```json
{ "status": "changed" }
```

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `400` | 새 비밀번호 변경 실패 (정책 위반 등) |
| `401` | 현재 비밀번호가 올바르지 않음 |
| `403` | 외부 로그인 사용자 (비밀번호 변경 불가) |
| `429` | 비율 제한 초과 |

---

## GET /api/v1/profile/activity

본인의 활동 로그를 반환합니다. `user_id` 기준의 cross-project 로그로, 여러 프로젝트에
걸친 활동이 함께 조회됩니다.

### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `limit` | int | 50 | 반환 개수 (1~200) |
| `before_id` | int | (없음) | 페이지네이션 커서. 이 ID 이전 항목 조회 |
| `resource_type` | string | (없음) | 리소스 유형 필터 (예: `auth`, `project`, `invitation`) |
| `action` | string | (없음) | 액션 필터 (예: `session_delete`) |

### 응답 (200 OK)

활동 로그 객체 배열을 반환합니다.

### 오류 응답

| 상태 코드 | 설명 |
|-----------|------|
| `401` | 유효하지 않거나 만료된 토큰 |
