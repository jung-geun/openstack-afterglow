---
title: 공유 스냅샷·네트워크 (Share Mgmt)
nav_order: 56
parent: API 레퍼런스
---

# 공유 스냅샷·네트워크 (Share Management) API

> 태그: `share-snapshots`, `share-networks`, `security-services`  
> 기본 경로: `/api/v1/share-snapshots`, `/api/v1/share-networks`, `/api/v1/security-services`

Manila share의 스냅샷, share 네트워크, security service를 관리합니다.
[파일 스토리지 API](file-storage.md)의 보조 리소스 계층에 해당합니다.

> **활성화 조건:** `config.toml`(또는 `afterglow.conf`) `[services] manila = true`.
> Manila 비활성화 시 이 라우터들도 마운트되지 않아 모든 경로가 `404`를 반환합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <access_token>` (로그인 응답의 access JWT) |
| `X-Project-Id` | (선택) 프로젝트 UUID — 생략 시 토큰의 프로젝트로 처리, 다른 값이면 rescope |

---

## 리소스 관계

```
share (파일 스토리지)
  └─ share-snapshot        시점 복제본 (생성·복원·삭제)

share-network              Neutron 네트워크에 연결된 Manila 네트워크
  └─ security-service      LDAP/Kerberos/AD — share-network에 attach/detach
```

- **share-snapshot**은 특정 share(`share_id`)에 종속됩니다.
- **security-service**는 독립 리소스로 생성한 뒤 **share-network에 attach**해야 효력이 생깁니다.
  attach/detach는 `security-service` 쪽 엔드포인트에서 `share_network_id`를 쿼리로 지정해 수행하며,
  연결 결과는 `ShareNetworkInfo.security_service_ids`에 반영됩니다.

---

## 목차

1. [공유 스냅샷 (Share Snapshots)](#1-공유-스냅샷-share-snapshots)
2. [공유 네트워크 (Share Networks)](#2-공유-네트워크-share-networks)
3. [Security Service](#3-security-service)

---

## 1. 공유 스냅샷 (Share Snapshots)

> 태그: `share-snapshots`  
> 기본 경로: `/api/v1/share-snapshots`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/share-snapshots` | 스냅샷 목록 (`share_id` 필터 가능) |
| `GET` | `/api/v1/share-snapshots/{snapshot_id}` | 스냅샷 상세 |
| `POST` | `/api/v1/share-snapshots` | 스냅샷 생성 |
| `POST` | `/api/v1/share-snapshots/{snapshot_id}/revert` | 스냅샷으로 복원 |
| `DELETE` | `/api/v1/share-snapshots/{snapshot_id}` | 스냅샷 삭제 |

### GET /api/v1/share-snapshots

프로젝트의 share 스냅샷 목록을 반환합니다. 응답은 캐시됩니다(`ttl_fast`).

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `share_id` | query | string | 아니오 | 특정 share의 스냅샷만 필터링 |
| `refresh` | query | boolean | 아니오 | 캐시 무시 여부 |

**응답 (200 OK)** — `ShareSnapshotInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "snap-1",
    "status": "available",
    "share_id": "uuid-string",
    "size": 20,
    "description": null,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 스냅샷 UUID |
| `name` | string | 스냅샷 이름 |
| `status` | string | 상태 (`available`, `creating`, `error` 등) |
| `share_id` | string | 원본 share UUID |
| `size` | integer | 크기 (GB) |
| `description` | string\|null | 설명 |
| `created_at` | string\|null | 생성 일시 (ISO 8601) |

### GET /api/v1/share-snapshots/{snapshot_id}

특정 스냅샷의 상세 정보를 반환합니다.

**오류**: `404` (스냅샷 없음)

### POST /api/v1/share-snapshots

새 share 스냅샷을 생성합니다.

**요청 본문** — `CreateShareSnapshotRequest`

```json
{
  "share_id": "uuid-string (필수)",
  "name": "string (필수, 1~255자)",
  "description": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|------|------|------|------|------|
| `share_id` | string | 예 | | 스냅샷을 생성할 share UUID |
| `name` | string | 예 | 1~255자 | 스냅샷 이름 |
| `description` | string | 아니오 | | 설명 |

**응답 (201 Created)** — `ShareSnapshotInfo` 객체

**오류**: `500` (생성 실패)

### POST /api/v1/share-snapshots/{snapshot_id}/revert

share를 지정한 스냅샷 시점으로 복원합니다. 복원 대상 share를 본문으로 명시해야 합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `snapshot_id` | path | string | 예 | 스냅샷 UUID |

**요청 본문** — `ShareSnapshotRevertRequest`

```json
{
  "share_id": "uuid-string (필수)"
}
```

**응답**: `204 No Content`

**오류**: `500` (복원 실패)

### DELETE /api/v1/share-snapshots/{snapshot_id}

스냅샷을 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `snapshot_id` | path | string | 예 | 스냅샷 UUID |

**응답**: `204 No Content`

---

## 2. 공유 네트워크 (Share Networks)

> 태그: `share-networks`  
> 기본 경로: `/api/v1/share-networks`

Manila share가 사용할 Neutron 네트워크/서브넷 연결을 정의합니다. DHSS(driver handles share servers) 모드에서 share 생성 시 필요합니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/share-networks` | Share 네트워크 목록 |
| `GET` | `/api/v1/share-networks/{share_network_id}` | Share 네트워크 상세 |
| `POST` | `/api/v1/share-networks` | Share 네트워크 생성 (분당 10회) |
| `DELETE` | `/api/v1/share-networks/{share_network_id}` | Share 네트워크 삭제 |

### GET /api/v1/share-networks

프로젝트의 share 네트워크 목록을 반환합니다. 응답은 캐시됩니다(`ttl_fast`).

**응답 (200 OK)** — `ShareNetworkInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "sn-1",
    "description": "",
    "neutron_net_id": "uuid-string",
    "neutron_subnet_id": "uuid-string",
    "network_type": "vxlan",
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "security_service_ids": ["uuid-string"]
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | Share 네트워크 UUID |
| `name` | string | 이름 |
| `description` | string | 설명 |
| `neutron_net_id` | string\|null | 연결된 Neutron 네트워크 UUID |
| `neutron_subnet_id` | string\|null | 연결된 Neutron 서브넷 UUID |
| `network_type` | string\|null | 네트워크 타입 |
| `status` | string | 상태 |
| `created_at` | string\|null | 생성 일시 (ISO 8601) |
| `security_service_ids` | array[string] | attach된 security service UUID 목록 |

### GET /api/v1/share-networks/{share_network_id}

특정 share 네트워크의 상세 정보를 반환합니다.

**오류**: `404` (없음)

### POST /api/v1/share-networks

새 share 네트워크를 생성합니다. **속도 제한: 분당 10회**

**요청 본문** — `CreateShareNetworkRequest`

```json
{
  "name": "string (필수, 1~255자)",
  "description": "string (선택)",
  "neutron_net_id": "uuid-string (필수)",
  "neutron_subnet_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|------|------|------|------|------|
| `name` | string | 예 | 1~255자 | 이름 |
| `description` | string | 아니오 | | 설명 |
| `neutron_net_id` | string | 예 | | 연결할 Neutron 네트워크 UUID |
| `neutron_subnet_id` | string | 예 | | 연결할 Neutron 서브넷 UUID |

**응답 (201 Created)** — `ShareNetworkInfo` 객체

**오류**

| 상태 | 원인 |
|------|------|
| `429` | 분당 생성 한도 초과 |
| `500` | 생성 실패 |

### DELETE /api/v1/share-networks/{share_network_id}

Share 네트워크를 삭제합니다. 연결된 share가 있으면 삭제가 실패할 수 있습니다.

**응답**: `204 No Content`

---

## 3. Security Service

> 태그: `security-services`  
> 기본 경로: `/api/v1/security-services`

LDAP/Kerberos/Active Directory 인증 서비스를 정의하고, share 네트워크에 연결(attach)합니다. 독립 리소스로 생성한 뒤 share 네트워크에 attach해야 해당 네트워크를 쓰는 share에 인증이 적용됩니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/security-services` | Security service 목록 |
| `POST` | `/api/v1/security-services` | Security service 생성 (분당 10회) |
| `DELETE` | `/api/v1/security-services/{security_service_id}` | Security service 삭제 |
| `POST` | `/api/v1/security-services/{security_service_id}/attach` | Share 네트워크에 연결 |
| `DELETE` | `/api/v1/security-services/{security_service_id}/detach` | Share 네트워크에서 해제 |

### GET /api/v1/security-services

프로젝트의 security service 목록을 반환합니다. 응답은 캐시됩니다(`ttl_fast`).

**응답 (200 OK)** — `SecurityServiceInfo[]` 배열

```json
[
  {
    "id": "uuid-string",
    "name": "ldap-1",
    "description": "",
    "type": "ldap",
    "dns_ip": "10.0.0.53",
    "server": "ldap.example.com",
    "domain": "example.com",
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | Security service UUID |
| `name` | string | 이름 |
| `description` | string | 설명 |
| `type` | string | 타입 (`ldap`, `kerberos`, `active_directory`) |
| `dns_ip` | string\|null | DNS 서버 IP |
| `server` | string\|null | 인증 서버 주소 |
| `domain` | string\|null | 도메인 |
| `status` | string | 상태 |
| `created_at` | string\|null | 생성 일시 (ISO 8601) |

### POST /api/v1/security-services

새 security service를 생성합니다. **속도 제한: 분당 10회**

**요청 본문** — `CreateSecurityServiceRequest`

```json
{
  "type": "ldap",
  "name": "string (필수, 1~255자)",
  "description": "string (선택)",
  "dns_ip": "string (선택)",
  "server": "string (선택)",
  "domain": "string (선택)",
  "user": "string (선택)",
  "password": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 제약 | 설명 |
|------|------|------|------|------|
| `type` | string | 예 | `ldap` \| `kerberos` \| `active_directory` | 인증 서비스 타입 |
| `name` | string | 예 | 1~255자 | 이름 |
| `description` | string | 아니오 | | 설명 |
| `dns_ip` | string | 아니오 | | DNS 서버 IP |
| `server` | string | 아니오 | | 인증 서버 주소 |
| `domain` | string | 아니오 | | 도메인 |
| `user` | string | 아니오 | | 바인드 계정 |
| `password` | string | 아니오 | | 바인드 계정 비밀번호 |

**응답 (201 Created)** — `SecurityServiceInfo` 객체

**오류**

| 상태 | 원인 |
|------|------|
| `429` | 분당 생성 한도 초과 |
| `500` | 생성 실패 |

### DELETE /api/v1/security-services/{security_service_id}

Security service를 삭제합니다. share 네트워크에 attach된 상태면 먼저 detach해야 할 수 있습니다.

**응답**: `204 No Content`

### POST /api/v1/security-services/{security_service_id}/attach

Security service를 지정한 share 네트워크에 연결합니다. 연결 후 대상 share 네트워크의 `security_service_ids`에 반영됩니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `security_service_id` | path | string | 예 | Security service UUID |
| `share_network_id` | query | string | 예 | 연결 대상 share 네트워크 UUID |

**응답 (200 OK)** — 갱신된 share 네트워크 정보

**오류**: `500` (연결 실패)

### DELETE /api/v1/security-services/{security_service_id}/detach

Security service를 지정한 share 네트워크에서 해제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `security_service_id` | path | string | 예 | Security service UUID |
| `share_network_id` | query | string | 예 | 해제 대상 share 네트워크 UUID |

**응답**: `204 No Content`

**오류**: `500` (해제 실패)
