# 인스턴스 (Instances) API

> 태그: `instances`  
> 기본 경로: `/api/instances`

Nova 인스턴스(가상 머신)의 생성, 조회, 제어, 삭제를 관리합니다. Afterglow의 핵심 기능인 OverlayFS 기반 VM 생성을 지원합니다.

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [기본 CRUD](#1-기본-crud)
2. [인스턴스 제어](#2-인스턴스-제어)
3. [볼륨 관리](#3-볼륨-관리)
4. [네트워크 인터페이스](#4-네트워크-인터페이스)
5. [보안 그룹](#5-보안-그룹)
6. [소유자 정보](#6-소유자-정보)

---

## 1. 기본 CRUD

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances` | 인스턴스 목록 (15초 캐시) |
| `GET` | `/api/instances/{instance_id}` | 특정 인스턴스 상세 정보 |
| `POST` | `/api/instances` | 인스턴스 동기 생성 |
| `POST` | `/api/instances/async` | 인스턴스 SSE 비동기 생성 |
| `DELETE` | `/api/instances/{instance_id}` | 인스턴스 삭제 (연관 리소스 포함) |

### GET /api/instances

프로젝트의 인스턴스 목록을 반환합니다. 응답은 15초간 캐시됩니다.

**응답 (200 OK)** — 배열

### GET /api/instances/{instance_id}

특정 인스턴스의 상세 정보를 반환합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `instance_id` | path | string | 예 | 인스턴스 UUID |

### POST /api/instances

인스턴스를 동기적으로 생성합니다. 모든 단계가 완료될 때까지 응답을 기다립니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "image_id": "string (필수)",
  "flavor_id": "string (필수)",
  "libraries": ["python311", "pytorch"],
  "strategy": "prebuilt",
  "network_id": "string (선택)",
  "key_name": "string (선택)",
  "admin_pass": "string (선택)",
  "availability_zone": "string (선택)",
  "boot_volume_size_gb": 20
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 인스턴스 이름 |
| `image_id` | string | 예 | Glance 이미지 UUID |
| `flavor_id` | string | 예 | Nova 플레이버 UUID |
| `libraries` | array[string] | 아니오 | 설치할 라이브러리 ID 목록 |
| `strategy` | string | 아니오 | `prebuilt` (사전 빌드 share 사용) 또는 `dynamic` (전용 share 신규 생성) |
| `network_id` | string | 아니오 | 연결할 네트워크 UUID. 생략 시 기본 네트워크 사용 |
| `key_name` | string | 아니오 | SSH 키페어 이름 |
| `admin_pass` | string | 아니오 | 관리자 비밀번호 |
| `availability_zone` | string | 아니오 | 가용 영역 |
| `boot_volume_size_gb` | integer | 아니오 | 부트 볼륨 크기 (GB, 기본값: 20) |

**전략 설명**

| 전략 | 설명 |
|------|------|
| `prebuilt` | 관리자가 미리 빌드한 read-only CephFS share에 접근 규칙을 추가합니다. 빠르고 스토리지 효율적입니다. |
| `dynamic` | VM 전용 read-write CephFS share를 새로 생성합니다. 격리가 완전하지만 생성 시간이 더 걸립니다. |

### POST /api/instances/async

인스턴스를 비동기적으로 생성하며 SSE(Server-Sent Events) 스트림으로 실시간 진행률을 전달합니다.

**요청 본문**: `POST /api/instances`와 동일

**SSE 이벤트 형식**

```json
{
  "step": "MANILA_PREPARING",
  "progress": 20,
  "message": "Manila 접근 규칙 설정 중...",
  "instance_id": null,
  "error": null
}
```

**step 값 목록**

| step | 진행률 | 설명 |
|------|--------|------|
| `MANILA_PREPARING` | 20% | Manila 라이브러리 share 접근 규칙 설정 |
| `BOOT_VOLUME_CREATING` | 45% | 부트 볼륨 생성 (이미지 기반) |
| `UPPER_VOLUME_CREATING` | 60% | OverlayFS upperdir 볼륨 생성 |
| `USERDATA_GENERATING` | 65% | cloud-init 사용자 데이터 생성 |
| `SERVER_CREATING` | 95% | Nova 서버 생성 |
| `ATTACHING_VOLUME` | 98% | 상위 볼륨 연결 |
| `FLOATING_IP_CREATING` | 99% | Floating IP 생성 및 연결 (tenant 네트워크인 경우) |
| `COMPLETED` | 100% | 완료. `instance_id` 포함 |
| `FAILED` | — | 실패. `error` 포함 |

**실패 시 롤백**

생성 도중 오류가 발생하면 이미 생성된 리소스를 역순으로 삭제합니다.

| 순서 | 롤백 대상 |
|------|-----------|
| 1 | Floating IP 삭제 |
| 2 | Nova 서버 삭제 |
| 3 | 부트 볼륨 / upper 볼륨 삭제 |
| 4 | Manila access rule 취소 |
| 5 | 동적(dynamic) share 삭제 |

### DELETE /api/instances/{instance_id}

인스턴스와 연관된 리소스(볼륨, Floating IP 등)를 함께 삭제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `instance_id` | path | string | 예 | 인스턴스 UUID |

**응답**: `204 No Content`

---

## 2. 인스턴스 제어

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/instances/{instance_id}/start` | 인스턴스 시작 |
| `POST` | `/api/instances/{instance_id}/stop` | 인스턴스 중지 |
| `POST` | `/api/instances/{instance_id}/reboot` | 인스턴스 재시작 |
| `GET` | `/api/instances/{instance_id}/console` | VNC 콘솔 URL 반환 |
| `GET` | `/api/instances/{instance_id}/log` | 콘솔 로그 반환 |

### POST /api/instances/{instance_id}/start

정지된 인스턴스를 시작합니다.

**응답 (200 OK)**

```json
{
  "status": "starting"
}
```

### POST /api/instances/{instance_id}/stop

실행 중인 인스턴스를 정지합니다.

**응답 (200 OK)**

```json
{
  "status": "stopping"
}
```

### POST /api/instances/{instance_id}/reboot

인스턴스를 재시작합니다.

**응답 (200 OK)**

```json
{
  "status": "rebooting"
}
```

### GET /api/instances/{instance_id}/console

인스턴스의 VNC 콘솔 접속 URL을 반환합니다.

**응답 (200 OK)**

```json
{
  "url": "vnc://...",
  "type": "novnc"
}
```

### GET /api/instances/{instance_id}/log

인스턴스의 콘솔 로그를 반환합니다.

| 파라미터 | 위치 | 타입 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `length` | query | integer | 100 | 반환할 로그 라인 수 |

**응답 (200 OK)**

```json
{
  "log": "콘솔 로그 텍스트..."
}
```

---

## 3. 볼륨 관리

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/volumes` | 연결된 볼륨 목록 |
| `POST` | `/api/instances/{instance_id}/volumes` | 볼륨 연결 |
| `DELETE` | `/api/instances/{instance_id}/volumes/{volume_id}` | 볼륨 해제 |

### GET /api/instances/{instance_id}/volumes

인스턴스에 연결된 볼륨 목록을 반환합니다.

**응답 (200 OK)** — 배열

### POST /api/instances/{instance_id}/volumes

인스턴스에 기존 볼륨을 연결합니다.

**요청 본문**

```json
{
  "volume_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `volume_id` | string | 예 | 연결할 볼륨 UUID |

### DELETE /api/instances/{instance_id}/volumes/{volume_id}

인스턴스에서 볼륨 연결을 해제합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `instance_id` | path | string | 예 | 인스턴스 UUID |
| `volume_id` | path | string | 예 | 볼륨 UUID |

**응답**: `204 No Content`

---

## 4. 네트워크 인터페이스

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/interfaces` | 네트워크 인터페이스 목록 |
| `POST` | `/api/instances/{instance_id}/interfaces` | 인터페이스 추가 |
| `DELETE` | `/api/instances/{instance_id}/interfaces/{port_id}` | 인터페이스 제거 |

### GET /api/instances/{instance_id}/interfaces

인스턴스의 네트워크 인터페이스(포트) 목록을 반환합니다.

**응답 (200 OK)** — 배열

### POST /api/instances/{instance_id}/interfaces

인스턴스에 새 네트워크 인터페이스를 추가합니다.

**요청 본문**

```json
{
  "net_id": "uuid-string (필수)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `net_id` | string | 예 | 연결할 네트워크 UUID |

### DELETE /api/instances/{instance_id}/interfaces/{port_id}

인스턴스에서 네트워크 인터페이스를 제거합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `instance_id` | path | string | 예 | 인스턴스 UUID |
| `port_id` | path | string | 예 | 포트 UUID |

**응답**: `204 No Content`

---

## 5. 보안 그룹

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/instances/{instance_id}/security-groups` | 인스턴스의 포트 및 보안 그룹 목록 |
| `POST` | `/api/instances/{instance_id}/ports/{port_id}/security-groups` | 포트 보안 그룹 업데이트 |

### GET /api/instances/{instance_id}/security-groups

인스턴스의 각 포트에 할당된 보안 그룹 목록을 반환합니다.

**응답 (200 OK)**

```json
[
  {
    "port_id": "uuid-string",
    "port_name": "port-name",
    "security_groups": [
      {
        "id": "uuid-string",
        "name": "default"
      }
    ]
  }
]
```

### POST /api/instances/{instance_id}/ports/{port_id}/security-groups

지정된 포트의 보안 그룹을 업데이트합니다. 기존 보안 그룹은 교체됩니다.

**요청 본문**

```json
{
  "security_group_ids": ["uuid-string", "uuid-string"]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `security_group_ids` | array[string] | 예 | 설정할 보안 그룹 UUID 목록 (기존 목록 교체) |

---

## 6. 소유자 정보

### GET /api/instances/{instance_id}/owner

인스턴스 소유자 정보를 반환합니다.

**응답 (200 OK)**

```json
{
  "user_id": "uuid-string",
  "user_name": "username",
  "project_id": "uuid-string",
  "project_name": "project-name"
}