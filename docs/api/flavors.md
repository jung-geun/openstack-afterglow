---
title: 플레이버 (Flavors)
parent: API 레퍼런스
nav_order: 33
---

# 플레이버 (Flavors) API

> 태그: `flavors`
> 기본 경로: `/api/v1/flavors`

Nova 플레이버(인스턴스 스펙) 카탈로그를 조회합니다.

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
| `GET` | `/api/v1/flavors` | Nova 플레이버 목록 반환 |

---

## GET /api/v1/flavors

프로젝트에서 사용 가능한 Nova 플레이버 목록을 반환합니다. GPU 여부, GPU 수 및 현재 프로젝트 쿼터 기준 생성 적격성(`eligibility`)이 포함됩니다. 응답은 캐시됩니다(`?refresh=true`로 강제 갱신 가능).

> **쿼터 판정 및 적용 범위 안내**:
> - 각 플레이버에는 현재 프로젝트의 잔여 인스턴스, vCPU, RAM 및 GPU 쿼터에 기반한 `eligibility.selectable` 상태와 차단 사유(`blockers`)가 포함됩니다.
> - Afterglow GPU 쿼터 및 단기 예약은 대시보드와 Afterglow 생성 요청을 보호합니다. 이미 Flavor 접근 권한(addTenantAccess)이 부여된 프로젝트의 CLI 또는 직접 Nova API 생성은 Nova 자체 쿼터 한계가 적용됩니다.
### 요청 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `Authorization` | 예 | `Bearer <access_token>` 형식의 access JWT |
| `X-Project-Id` | 아니오 | 프로젝트 UUID (생략 시 토큰의 프로젝트) |

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
    "eligibility": {
      "selectable": true,
      "requirements": { "instances": 1, "cores": 2, "ram_mb": 2048, "gpus": {} },
      "remaining": { "instances": 10, "cores": 18, "ram_mb": 30720, "gpus": {} },
      "blockers": []
    },
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
| `extra_specs` | object | 추가 스펙 (GPU `pci_passthrough:alias` 등 포함) |
| `is_gpu` | boolean | GPU 플레이버 여부 (이름이 `gpu.`로 시작) |
| `gpu_count` | integer | GPU 수 (0이면 GPU 없음) |
