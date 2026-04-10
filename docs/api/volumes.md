# 볼륨 (Volumes) API

> 태그: `volumes`, `volume-backups`, `volume-snapshots`  
> 기본 경로: `/api/volumes`, `/api/volumes/backups`, `/api/volume-snapshots`

Cinder 블록 스토리지 볼륨, 백업, 스냅샷을 관리합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [볼륨](#1-볼륨)
2. [볼륨 백업](#2-볼륨-백업)
3. [볼륨 스냅샷](#3-볼륨-스냅샷)

---

## 1. 볼륨

> 태그: `volumes`  
> 기본 경로: `/api/volumes`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volumes` | 볼륨 목록 (15초 캐시) |
| `GET` | `/api/volumes/{volume_id}` | 볼륨 상세 정보 |
| `POST` | `/api/volumes` | 볼륨 생성 |
| `DELETE` | `/api/volumes/{volume_id}` | 볼륨 삭제 |

### GET /api/volumes

프로젝트의 Cinder 볼륨 목록을 반환합니다. 응답은 15초간 캐시됩니다.

**응답 (200 OK)** — `VolumeInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "volume-name",
    "status": "in-use",
    "size": 50,
    "volume_type": "ceph",
    "attachments": [
      {
        "server_id": "uuid-string",
        "device": "/dev/vdb"
      }
    ],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 볼륨 UUID |
| `name` | string | 볼륨 이름 |
| `status` | string | 상태 (`available`, `in-use`, `error` 등) |
| `size` | integer | 크기 (GB) |
| `volume_type` | string | 볼륨 타입 |
| `attachments` | array | 연결 정보 |
| `created_at` | string | 생성 일시 (ISO 8601) |

### GET /api/volumes/{volume_id}

특정 볼륨의 상세 정보를 반환합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `volume_id` | path | string | 예 | 볼륨 UUID |

### POST /api/volumes

새 Cinder 볼륨을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "size_gb": 50,
  "availability_zone": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 볼륨 이름 |
| `size_gb` | integer | 예 | 크기 (GB) |
| `availability_zone` | string | 아니오 | 가용 영역 |

**응답 (201 Created)** — `VolumeInfo` 객체

### DELETE /api/volumes/{volume_id}

볼륨을 삭제합니다. `in-use` 상태의 볼륨은 삭제할 수 없습니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `volume_id` | path | string | 예 | 볼륨 UUID |

**응답**: `204 No Content`

---

## 2. 볼륨 백업

> 태그: `volume-backups`  
> 기본 경로: `/api/volumes/backups`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volumes/backups` | 볼륨 백업 목록 |
| `GET` | `/api/volumes/backups/{backup_id}` | 백업 상세 정보 |
| `POST` | `/api/volumes/backups` | 백업 생성 |
| `DELETE` | `/api/volumes/backups/{backup_id}` | 백업 삭제 |
| `POST` | `/api/volumes/backups/{backup_id}/restore` | 백업 복원 |

### GET /api/volumes/backups

프로젝트의 Cinder 볼륨 백업 목록을 반환합니다.

**응답 (200 OK)** — 배열

```json
[
  {
    "id": "uuid-string",
    "name": "backup-name",
    "status": "available",
    "size": 50,
    "volume_id": "uuid-string",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 백업 UUID |
| `name` | string | 백업 이름 |
| `status` | string | 상태 (`available`, `creating`, `restoring`, `error` 등) |
| `size` | integer | 크기 (GB) |
| `volume_id` | string | 원본 볼륨 UUID |
| `created_at` | string | 생성 일시 (ISO 8601) |

### GET /api/volumes/backups/{backup_id}

특정 백업의 상세 정보를 반환합니다.

### POST /api/volumes/backups

새 볼륨 백업을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "volume_id": "uuid-string (필수)",
  "description": "string (선택)",
  "force": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 백업 이름 |
| `volume_id` | string | 예 | 백업할 볼륨 UUID |
| `description` | string | 아니오 | 설명 |
| `force` | boolean | 아니오 | `in-use` 상태의 볼륨도 강제 백업 (기본값: `false`) |

**응답 (201 Created)**

```json
{
  "id": "uuid-string",
  "name": "backup-name",
  "status": "creating",
  "volume_id": "uuid-string"
}
```

### POST /api/volumes/backups/{backup_id}/restore

백업을 새 볼륨으로 복원합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "volume_id": "uuid-string (선택, 기존 볼륨에 덮어쓸 경우)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 아니오 | 복원될 새 볼륨 이름 |
| `volume_id` | string | 아니오 | 기존 볼륨에 덮어쓸 경우 해당 볼륨 UUID |

**응답 (200 OK)**

```json
{
  "restore": {
    "backup_id": "uuid-string",
    "volume_id": "uuid-string",
    "volume_name": "restored-volume"
  }
}
```

### DELETE /api/volumes/backups/{backup_id}

백업을 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `backup_id` | path | string | 예 | 백업 UUID |

**응답**: `204 No Content`

---

## 3. 볼륨 스냅샷

> 태그: `volume-snapshots`  
> 기본 경로: `/api/volume-snapshots`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/volume-snapshots` | 스냅샷 목록 |
| `GET` | `/api/volume-snapshots/{snapshot_id}` | 스냅샷 상세 정보 |
| `POST` | `/api/volume-snapshots` | 스냅샷 생성 |
| `DELETE` | `/api/volume-snapshots/{snapshot_id}` | 스냅샷 삭제 |

### GET /api/volume-snapshots

프로젝트의 Cinder 볼륨 스냅샷 목록을 반환합니다.

**응답 (200 OK)** — 배열

```json
[
  {
    "id": "uuid-string",
    "name": "snapshot-name",
    "status": "available",
    "size": 50,
    "volume_id": "uuid-string",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 스냅샷 UUID |
| `name` | string | 스냅샷 이름 |
| `status` | string | 상태 (`available`, `creating`, `error` 등) |
| `size` | integer | 크기 (GB) |
| `volume_id` | string | 원본 볼륨 UUID |
| `created_at` | string | 생성 일시 (ISO 8601) |

### GET /api/volume-snapshots/{snapshot_id}

특정 스냅샷의 상세 정보를 반환합니다.

### POST /api/volume-snapshots

새 볼륨 스냅샷을 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "volume_id": "uuid-string (필수)",
  "description": "string (선택)",
  "force": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 스냅샷 이름 |
| `volume_id` | string | 예 | 스냅샷을 생성할 볼륨 UUID |
| `description` | string | 아니오 | 설명 |
| `force` | boolean | 아니오 | `in-use` 상태의 볼륨도 강제 스냅샷 (기본값: `false`) |

**응답 (201 Created)**

### DELETE /api/volume-snapshots/{snapshot_id}

스냅샷을 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `snapshot_id` | path | string | 예 | 스냅샷 UUID |

**응답**: `204 No Content`