# 컨테이너 (Containers) API

> 태그: `clusters`, `containers`  
> 기본 경로: `/api/clusters`, `/api/containers`

Magnum 쿠버네티스 클러스터와 Zun 컨테이너를 관리합니다. **config.toml에서 각 서비스가 활성화된 경우에만 사용 가능합니다.**

---

## 인증 헤더

| 헤더 | 설명 |
|------|------|
| `X-Auth-Token` | Keystone 인증 토큰 |
| `X-Project-Id` | OpenStack 프로젝트 UUID |

---

## 목차

1. [쿠버네티스 클러스터 (Magnum)](#1-쿠버네티스-클러스터-magnum)
2. [컨테이너 (Zun)](#2-컨테이너-zun)

---

## 1. 쿠버네티스 클러스터 (Magnum)

> 태그: `clusters`  
> 기본 경로: `/api/clusters`

**config.toml에서 Magnum 서비스가 활성화된 경우에만 사용 가능합니다.**

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/clusters` | 클러스터 목록 |
| `POST` | `/api/clusters` | 클러스터 생성 |
| `GET` | `/api/clusters/{cluster_id}` | 클러스터 상세 |
| `DELETE` | `/api/clusters/{cluster_id}` | 클러스터 삭제 |

### GET /api/clusters

프로젝트의 Magnum 쿠버네티스 클러스터 목록을 반환합니다.

**응답 (200 OK)** — 배열

### POST /api/clusters

새 쿠버네티스 클러스터를 생성합니다.

**요청 본문**

```json
{
  "name": "string (필수)",
  "cluster_template_id": "uuid-string (필수)",
  "node_count": 1,
  "master_count": 1,
  "keypair": "string (선택)"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 클러스터 이름 |
| `cluster_template_id` | string | 예 | 클러스터 템플릿 UUID |
| `node_count` | integer | 아니오 | 워커 노드 수 |
| `master_count` | integer | 아니오 | 마스터 노드 수 |
| `keypair` | string | 아니오 | SSH 키페어 이름 |

### GET /api/clusters/{cluster_id}

특정 클러스터의 상세 정보를 반환합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|----------|------|------|------|------|
| `cluster_id` | path | string | 예 | 클러스터 UUID |

### DELETE /api/clusters/{cluster_id}

클러스터를 삭제합니다.

**응답**: `204 No Content`

---

## 2. 컨테이너 (Zun)

> 태그: `containers`  
> 기본 경로: `/api/containers`

**config.toml에서 Zun 서비스가 활성화된 경우에만 사용 가능합니다.**

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/containers` | 컨테이너 목록 |
| `POST` | `/api/containers` | 컨테이너 생성 |
| `GET` | `/api/containers/{container_id}` | 컨테이너 상세 |
| `DELETE` | `/api/containers/{container_id}` | 컨테이너 삭제 |
| `POST` | `/api/containers/{container_id}/start` | 컨테이너 시작 |
| `POST` | `/api/containers/{container_id}/stop` | 컨테이너 중지 |
| `POST` | `/api/containers/{container_id}/restart` | 컨테이너 재시작 |

### GET /api/containers

프로젝트의 Zun 컨테이너 목록을 반환합니다.

**응답 (200 OK)** — 배열

### POST /api/containers

새 컨테이너를 생성합니다.

**요청 본문**

```json
{
  "name": "string (선택)",
  "image": "string (필수)",
  "command": "string (선택)",
  "cpu": 1.0,
  "memory": 512
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 아니오 | 컨테이너 이름 |
| `image` | string | 예 | 컨테이너 이미지 |
| `command` | string | 아니오 | 실행 명령어 |
| `cpu` | float | 아니오 | CPU 코어 수 |
| `memory` | integer | 아니오 | 메모리 (MB) |

### GET /api/containers/{container_id}

특정 컨테이너의 상세 정보를 반환합니다.

### DELETE /api/containers/{container_id}

컨테이너를 삭제합니다.

**응답**: `204 No Content`

### POST /api/containers/{container_id}/start

정지된 컨테이너를 시작합니다.

### POST /api/containers/{container_id}/stop

실행 중인 컨테이너를 정지합니다.

### POST /api/containers/{container_id}/restart

컨테이너를 재시작합니다.