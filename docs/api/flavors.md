# 플레이버 (Flavors) API

> 태그: `flavors`  
> 기본 경로: `/api/flavors`

Nova 플레이버(인스턴스 스펙) 카탈로그를 조회합니다.

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
| `GET` | `/api/flavors` | Nova 플레이버 목록 반환 |

---

## GET /api/flavors

프로젝트에서 사용 가능한 Nova 플레이버 목록을 반환합니다. GPU 여부 및 GPU 수도 포함됩니다.

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
    "name": "m1.small",
    "vcpus": 2,
    "ram": 2048,
    "disk": 20,
    "is_public": true,
    "extra_specs": {},
    "is_gpu": false,
    "gpu_count": 0
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 플레이버 UUID |
| `name` | string | 플레이버 이름 |
| `vcpus` | integer | vCPU 수 |
| `ram` | integer | RAM (MB) |
| `disk` | integer | 루트 디스크 (GB) |
| `is_public` | boolean | 공개 여부 |
| `extra_specs` | object | 추가 스펙 (GPU 리소스 정보 등 포함) |
| `is_gpu` | boolean | GPU 플레이버 여부 |
| `gpu_count` | integer | GPU 수 (0이면 GPU 없음) |