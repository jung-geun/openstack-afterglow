# 이미지 (Images) API

> 태그: `images`  
> 기본 경로: `/api/images`

Glance 이미지 카탈로그를 조회합니다.

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
| `GET` | `/api/images` | Glance 이미지 목록 반환 |

---

## GET /api/images

프로젝트에서 사용 가능한 Glance 이미지 목록을 반환합니다. 응답은 300초간 캐시됩니다.

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
    "name": "Ubuntu 22.04",
    "status": "active",
    "size": 2147483648,
    "min_disk": 20,
    "min_ram": 512,
    "disk_format": "qcow2",
    "os_distro": "ubuntu",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 이미지 UUID |
| `name` | string | 이미지 이름 |
| `status` | string | 상태 (`active`, `queued`, `saving` 등) |
| `size` | integer | 바이트 단위 크기 |
| `min_disk` | integer | 최소 디스크 요구량 (GB) |
| `min_ram` | integer | 최소 RAM 요구량 (MB) |
| `disk_format` | string | 디스크 포맷 (`qcow2`, `raw` 등) |
| `os_distro` | string | OS 배포판 (`ubuntu`, `centos` 등) |
| `created_at` | string | 생성 일시 (ISO 8601) |