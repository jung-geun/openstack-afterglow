---
title: 이미지 (Images)
parent: API 레퍼런스
nav_order: 32
---

# 이미지 (Images) API

> 태그: `images`
> 기본 경로: `/api/v1/images`

Glance 이미지 카탈로그를 조회하고, 이미지 업로드·메타데이터 수정·활성화 상태 변경·공유 멤버 관리를 수행합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <access_token>` (로그인 응답의 access JWT) |
| `X-Project-Id` | (선택) 프로젝트 UUID — 생략 시 토큰의 프로젝트로 처리, 다른 값이면 rescope |

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/images` | 이미지 목록 |
| `POST` | `/api/v1/images` | 이미지 업로드 (3/분) |
| `GET` | `/api/v1/images/{image_id}` | 이미지 상세 |
| `DELETE` | `/api/v1/images/{image_id}` | 이미지 삭제 |
| `PATCH` | `/api/v1/images/{image_id}` | 이미지 기본 메타데이터 수정 |
| `PATCH` | `/api/v1/images/{image_id}/properties` | 임의 properties 추가/삭제 |
| `POST` | `/api/v1/images/{image_id}/deactivate` | 이미지 비활성화 |
| `POST` | `/api/v1/images/{image_id}/reactivate` | 이미지 재활성화 |
| `GET` | `/api/v1/images/{image_id}/members` | 공유 멤버(프로젝트) 목록 |
| `POST` | `/api/v1/images/{image_id}/members` | 공유 프로젝트 추가 |
| `DELETE` | `/api/v1/images/{image_id}/members/{member_id}` | 공유 프로젝트 삭제 |

---

## GET /api/v1/images

프로젝트에서 사용 가능한 Glance 이미지 목록을 반환합니다. 응답은 장기간 캐시됩니다(`?refresh=true`로 강제 갱신 가능).

### 응답 (200 OK) — `ImageInfo` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "Ubuntu 22.04",
    "status": "active",
    "size": 2147483648,
    "min_disk": 20,
    "min_ram": 512,
    "disk_format": "qcow2",
    "os_type": "linux",
    "os_distro": "ubuntu",
    "created_at": "2024-01-01T00:00:00Z",
    "owner": "uuid-string",
    "visibility": "private"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 이미지 UUID |
| `name` | string | 이미지 이름 |
| `status` | string | 상태 (`active`, `queued`, `saving`, `deactivated` 등) |
| `size` | integer \| null | 바이트 단위 크기 |
| `min_disk` | integer | 최소 디스크 요구량 (GB) |
| `min_ram` | integer | 최소 RAM 요구량 (MB) |
| `disk_format` | string \| null | 디스크 포맷 (`qcow2`, `raw` 등) |
| `os_type` | string \| null | OS 타입 |
| `os_distro` | string \| null | OS 배포판 (`ubuntu`, `centos` 등) |
| `created_at` | string \| null | 생성 일시 (ISO 8601) |
| `owner` | string \| null | 소유 프로젝트 UUID |
| `visibility` | string \| null | `private` \| `public` \| `shared` \| `community` |

---

## POST /api/v1/images

이미지 파일을 업로드합니다(`multipart/form-data`). **속도 제한: 3회/분.**

### 요청 (multipart/form-data)

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `file` | file | 예 | — | 업로드할 이미지 파일 |
| `name` | string | 예 | — | 이미지 이름 (공백 불가) |
| `disk_format` | string | 아니오 | `raw` | 허용 포맷만 가능(`raw`/`qcow2`/`vmdk` 등). 미허용 시 `400` |
| `visibility` | string | 아니오 | `private` | `private`/`public`/`shared`/`community` |
| `os_distro` | string | 아니오 | — | OS 배포판. 지정 시 이미지 property로 설정 |

> `public`/`community` 가시성은 **시스템 관리자만** 설정할 수 있습니다(그 외 `403`). 파일 크기가 서버 설정 상한(`app_max_upload_gb`)을 초과하면 `413`.

### 응답 (201 Created)

```json
{ "id": "uuid-string", "name": "my-image", "status": "queued", "disk_format": "raw" }
```

**오류**: `400`(disk_format/visibility/이름 검증), `403`(권한), `413`(크기 초과), `500`(업로드 실패)

---

## GET /api/v1/images/{image_id}

이미지 상세 정보를 반환합니다.

### 응답 (200 OK) — `ImageDetail`

`ImageInfo`의 모든 필드에 더해 다음을 포함합니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `checksum` | string \| null | MD5 체크섬 |
| `container_format` | string \| null | 컨테이너 포맷 |
| `virtual_size` | integer \| null | 가상 크기(바이트) |
| `updated_at` | string \| null | 수정 일시 |
| `protected` | boolean | 삭제 보호 여부 |
| `tags` | array[string] | 태그 목록 |
| `properties` | object | 임의 메타데이터 |
| `os_hash_algo` / `os_hash_value` | string \| null | 해시 알고리즘/값 |
| `direct_url` | string \| null | 직접 접근 URL |

**오류**: `404 Not Found`

---

## DELETE /api/v1/images/{image_id}

이미지를 삭제합니다.

**응답**: `204 No Content` · **오류**: `500`(삭제 실패)

---

## PATCH /api/v1/images/{image_id}

이미지 기본 메타데이터를 수정합니다. 값을 지정한 필드만 갱신됩니다.

### 요청 본문

```json
{ "name": "new-name", "os_distro": "ubuntu", "os_type": "linux", "min_disk": 20, "min_ram": 1024, "visibility": "private" }
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string \| null | 이미지 이름 |
| `os_distro` | string \| null | OS 배포판 |
| `os_type` | string \| null | OS 타입 |
| `min_disk` | integer \| null | 최소 디스크(GB) |
| `min_ram` | integer \| null | 최소 RAM(MB) |
| `visibility` | string \| null | 가시성 |

**응답 (200 OK)** — 갱신된 `ImageInfo`

---

## PATCH /api/v1/images/{image_id}/properties

이미지의 임의 property를 추가/수정/삭제합니다. **소유자 또는 시스템 관리자만** 가능합니다.

### 요청 본문

```json
{ "set": { "hw_qemu_guest_agent": "yes" }, "remove": ["old_key"] }
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `set` | object \| null | 추가/수정할 key-value |
| `remove` | array[string] \| null | 삭제할 key 목록 |

**응답 (200 OK)** — 갱신된 `ImageDetail`

**오류**: `403`(본인 소유 아님), `404`(없음), `400`(수정 실패)

---

## POST /api/v1/images/{image_id}/deactivate · reactivate

본인 프로젝트가 소유한 이미지를 비활성화/재활성화합니다. 비활성 이미지는 부팅에 사용할 수 없습니다.

**응답 (200 OK)**: `{"status": "deactivated"}` 또는 `{"status": "active"}`

**오류**: `403`(본인 소유 아님), `404`(없음), `400`(처리 실패)

---

## 이미지 멤버 (공유 프로젝트 관리)

`shared` 가시성 이미지를 특정 프로젝트에 공유하기 위한 멤버 관리입니다.

### GET /api/v1/images/{image_id}/members

공유 멤버(프로젝트) 목록을 반환합니다.

### POST /api/v1/images/{image_id}/members

**요청 본문**

```json
{ "member": "project-uuid" }
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `member` | string | 예 | 공유 대상 프로젝트 UUID |

**응답**: `201 Created`

### DELETE /api/v1/images/{image_id}/members/{member_id}

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `image_id` | path | string | 예 | 이미지 UUID |
| `member_id` | path | string | 예 | 공유 프로젝트 UUID |

**응답**: `204 No Content`
