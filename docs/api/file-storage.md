# 파일 스토리지 (File Storage) API

> 태그: `file-storage`  
> 기본 경로: `/api/file-storage`

Manila 공유 파일 시스템(CephFS)을 관리합니다. **config.toml에서 Manila 서비스가 활성화된 경우에만 사용 가능합니다.**

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [파일 스토리지 CRUD](#1-파일-스토리지-crud)
2. [접근 규칙 (Access Rules)](#2-접근-규칙-access-rules)
3. [쿼터 및 타입](#3-쿼터-및-타입)

---

## 1. 파일 스토리지 CRUD

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/file-storage` | 파일 스토리지 목록 |
| `GET` | `/api/file-storage/{file_storage_id}` | 파일 스토리지 상세 |
| `POST` | `/api/file-storage` | 파일 스토리지 생성 |
| `DELETE` | `/api/file-storage/{file_storage_id}` | 파일 스토리지 삭제 |

### GET /api/file-storage

프로젝트의 Manila share 목록을 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `refresh` | query | boolean | `false` | 캐시 무시 여부 |

**응답 (200 OK)** — `FileStorageInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "union-prebuilt-python311",
    "status": "available",
    "size": 20,
    "share_proto": "CEPHFS",
    "export_locations": ["10.0.0.1:/volumes/_nogroup/..."],
    "metadata": {
      "union_type": "prebuilt",
      "union_library": "python311"
    },
    "library_name": "python311",
    "library_version": "3.11",
    "built_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | Share UUID |
| `name` | string | Share 이름 |
| `status` | string | 상태 (`available`, `creating`, `error` 등) |
| `size` | integer | 크기 (GB) |
| `share_proto` | string | 프로토콜 (`CEPHFS`, `NFS`) |
| `export_locations` | array[string] | 마운트 경로 목록 |
| `metadata` | object | 메타데이터 (Afterglow 전용 필드 포함) |
| `library_name` | string\|null | Afterglow 라이브러리 ID |
| `library_version` | string\|null | 라이브러리 버전 |
| `built_at` | string\|null | 빌드 일시 |

### GET /api/file-storage/{file_storage_id}

특정 파일 스토리지의 상세 정보를 반환합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `file_storage_id` | path | string | 예 | 파일 스토리지 UUID |

### POST /api/file-storage

새 Manila share를 생성합니다. **속도 제한: 분당 5회**

**요청 본문**

```json
{
  "name": "string (필수, 1~255자)",
  "size_gb": 20,
  "share_type": "cephfstype (선택, 기본값: config.toml 설정)",
  "share_network_id": "uuid-string (선택, 기본값: config.toml 설정)",
  "metadata": {},
  "share_proto": "CEPHFS"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | Share 이름 (1~255자) |
| `size_gb` | integer | 예 | 크기 (GB, 1~16384) |
| `share_type` | string | 아니오 | Manila share 타입. 기본값: config.toml의 `manila_share_type` |
| `share_network_id` | string | 아니오 | Share 네트워크 UUID. 기본값: config.toml의 `manila_share_network_id` |
| `metadata` | object | 아니오 | 메타데이터 |
| `share_proto` | string | 아니오 | 프로토콜 (`CEPHFS` 또는 `NFS`, 기본값: `CEPHFS`) |

**응답 (201 Created)** — `FileStorageInfo` 객체

### DELETE /api/file-storage/{file_storage_id}

파일 스토리지를 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `file_storage_id` | path | string | 예 | 파일 스토리지 UUID |

**응답**: `204 No Content`

---

## 2. 접근 규칙 (Access Rules)

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/file-storage/{file_storage_id}/access-rules` | 접근 규칙 목록 |
| `POST` | `/api/file-storage/{file_storage_id}/access-rules` | 접근 규칙 추가 |
| `DELETE` | `/api/file-storage/{file_storage_id}/access-rules/{access_id}` | 접근 규칙 삭제 |

### GET /api/file-storage/{file_storage_id}/access-rules

파일 스토리지의 접근 규칙 목록을 반환합니다.

**응답 (200 OK)** — 배열

### POST /api/file-storage/{file_storage_id}/access-rules

파일 스토리지에 접근 규칙을 추가합니다. CephX 인증 또는 IP 기반 접근 제어가 가능합니다.

**요청 본문**

```json
{
  "access_to": "string (필수)",
  "access_level": "ro",
  "access_type": "cephx"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `access_to` | string | 예 | 접근 대상 (CephX ID 또는 IP/CIDR) |
| `access_level` | string | 아니오 | 접근 수준 (`ro` 읽기 전용, `rw` 읽기/쓰기, 기본값: `ro`) |
| `access_type` | string | 아니오 | 접근 타입 (`cephx`, `ip`, 기본값: `cephx`) |

**응답 (201 Created)**

### DELETE /api/file-storage/{file_storage_id}/access-rules/{access_id}

접근 규칙을 삭제(회수)합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `file_storage_id` | path | string | 예 | 파일 스토리지 UUID |
| `access_id` | path | string | 예 | 접근 규칙 UUID |

**응답**: `204 No Content`

---

## 3. 쿼터 및 타입

### GET /api/file-storage/quota

프로젝트의 Manila 파일 스토리지 쿼터를 반환합니다.

**응답 (200 OK)**

```json
{
  "gigabytes": {"limit": 1000, "in_use": 200},
  "shares": {"limit": 50, "in_use": 10},
  "snapshots": {"limit": 50, "in_use": 5}
}
```

### GET /api/file-storage/types

사용 가능한 Manila share 타입 목록을 반환합니다.

**응답 (200 OK)** — 배열