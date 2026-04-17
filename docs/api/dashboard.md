# 대시보드 및 공통 (Dashboard & Common) API

> 태그: `dashboard`, `libraries`, `site`, `user-dashboard`  
> 기본 경로: `/api/dashboard`, `/api/libraries`, `/api/site-config`, `/api/user-dashboard`

프로젝트 대시보드 요약, 사용자 대시보드, 라이브러리 카탈로그, 사이트 설정을 제공합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [프로젝트 대시보드](#1-프로젝트-대시보드)
2. [사용자 대시보드](#2-사용자-대시보드)
3. [라이브러리 카탈로그](#3-라이브러리-카탈로그)
4. [사이트 설정](#4-사이트-설정)

---

## 1. 프로젝트 대시보드

> 태그: `dashboard`  
> 기본 경로: `/api/dashboard`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/dashboard/summary` | 인스턴스 수, 컴퓨트/스토리지 한도, GPU 사용량 |
| `GET` | `/api/dashboard/config` | 프론트엔드 설정 (새로고침 간격 등) |

### GET /api/dashboard/summary

프로젝트의 리소스 사용량 요약을 반환합니다. Nova 한도, Cinder 한도, 인스턴스 상태별 집계를 포함합니다.

**응답 (200 OK)**

```json
{
  "instances": {
    "total": 10,
    "active": 8,
    "shutoff": 1,
    "error": 1
  },
  "compute": {
    "instances": {"limit": 20, "in_use": 10},
    "cores": {"limit": 40, "in_use": 20},
    "ram": {"limit": 81920, "in_use": 40960}
  },
  "storage": {
    "volumes": {"limit": 10, "in_use": 5},
    "gigabytes": {"limit": 1000, "in_use": 250}
  },
  "gpu_used": 2
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `instances` | object | 상태별 인스턴스 수 |
| `compute` | object | Nova 컴퓨트 쿼터 및 사용량 |
| `storage` | object | Cinder 스토리지 쿼터 및 사용량 |
| `gpu_used` | integer | 사용 중인 GPU 인스턴스 수 |

### GET /api/dashboard/config

프론트엔드에서 사용하는 설정값을 반환합니다.

**응답 (200 OK)**

```json
{
  "refresh_interval_ms": 5000,
  "manila_enabled": true,
  "magnum_enabled": false,
  "zun_enabled": false
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `refresh_interval_ms` | integer | 대시보드 자동 새로고침 간격 (ms) |
| `manila_enabled` | boolean | Manila 파일 스토리지 서비스 활성화 여부 |
| `magnum_enabled` | boolean | Magnum 컨테이너 인프라 서비스 활성화 여부 |
| `zun_enabled` | boolean | Zun 컨테이너 서비스 활성화 여부 |

---

## 2. 사용자 대시보드

> 태그: `user-dashboard`  
> 기본 경로: `/api/user-dashboard`

### GET /api/user-dashboard

현재 사용자의 인스턴스, 볼륨 등 개인 리소스 요약을 반환합니다.

**응답 (200 OK)**

사용자가 소유한 인스턴스, 볼륨, 파일 스토리지 목록과 요약 통계를 포함합니다.

---

## 3. 라이브러리 카탈로그

> 태그: `libraries`  
> 기본 경로: `/api/libraries`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/libraries` | 라이브러리 카탈로그 목록 |
| `GET` | `/api/libraries/shares` | 사전 빌드된 Manila share 목록 |

### GET /api/libraries

Afterglow 라이브러리 카탈로그를 반환합니다. 각 라이브러리의 사전 빌드 share 가용 여부를 포함합니다.

**응답 (200 OK)** — `LibraryConfig[]` 배열

```json
[
  {
    "id": "python311",
    "name": "Python 3.11",
    "version": "3.11",
    "packages": ["numpy", "pandas", "scipy"],
    "depends_on": [],
    "file_storage_id": "uuid-string",
    "available_prebuilt": true
  },
  {
    "id": "pytorch",
    "name": "PyTorch",
    "version": "2.1",
    "packages": ["torch", "torchvision", "torchaudio"],
    "depends_on": ["python311"],
    "file_storage_id": null,
    "available_prebuilt": false
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 라이브러리 식별자 (예: `python311`) |
| `name` | string | 라이브러리 표시명 |
| `version` | string | 버전 |
| `packages` | array[string] | 포함된 pip 패키지 목록 |
| `depends_on` | array[string] | 의존하는 다른 라이브러리 ID |
| `file_storage_id` | string\|null | 사전 빌드된 share UUID. 없으면 `null` |
| `available_prebuilt` | boolean | 사전 빌드 share 사용 가능 여부 |

### GET /api/libraries/shares

사전 빌드된 Manila share 목록을 반환합니다. 관리자가 빌드한 라이브러리 share를 확인할 수 있습니다.

**응답 (200 OK)** — 배열

---

## 4. 사이트 설정

> 태그: `site`  
> 기본 경로: `/api/site-config`

### GET /api/site-config

프론트엔드에서 사용하는 전역 사이트 설정을 반환합니다. 인증이 필요하지 않을 수 있습니다.

**응답 (200 OK)**

```json
{
  "site_name": "Afterglow",
  "refresh_interval_ms": 5000,
  "manila_enabled": true,
  "magnum_enabled": false,
  "zun_enabled": false
}