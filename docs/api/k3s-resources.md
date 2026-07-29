---
title: k3s 리소스 관리
parent: API 레퍼런스
nav_order: 41
---

# k3s 리소스 관리

k3s 클러스터 **내부의 Kubernetes 리소스**(Namespace, Pod, Deployment, ReplicaSet, Service, ConfigMap, Secret)를 조회·조작하고 Cloud Shell 을 여는 프록시성 API입니다. Afterglow 백엔드가 클러스터의 저장된 kubeconfig 로 in-cluster API 서버에 접속하여 사용자를 대신 작업합니다 — 사용자가 kubeconfig 를 직접 내려받지 않고도 웹에서 리소스를 다룰 수 있습니다.

클러스터 라이프사이클(생성/삭제/스케일/헬스/노드그룹/인증서)은 [k3s 클러스터 (k3s)](k3s.md) 문서를 참고하세요.

> **활성화 조건:** `afterglow.conf [services] k3s = true`

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| 기본 경로 | `/api/v1/k3s/clusters` |
| 인증 | 모든 엔드포인트에 `Authorization: Bearer <access_token>` 헤더 필요 (`X-Project-Id`는 선택) |
| 소유권 검증 | 모든 요청은 `get_cluster(project_id, cluster_id)` 로 클러스터가 현재 프로젝트 소속인지 확인. 불일치/미존재 시 `404` |
| 접근 방식 | 클러스터 kubeconfig 로 in-cluster K8s API 프록시 |
| Tags | `k3s-pods`, `k3s-workloads`, `k3s-services`, `k3s-configmaps`, `k3s-secrets`, `k3s-shell` |

> 조작(create/update/delete/scale/restart, shell 티켓)은 `activity_recorder` 로 audit 로깅됩니다. 단, **Secret data 는 로그 extra 에 포함하지 않습니다**(이름/namespace 만 기록).

---

## Namespace

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/{cluster_id}/namespaces` | 클러스터의 네임스페이스 목록 |

---

## Pod

| 메서드 | 경로 | 응답 | 설명 |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/pods` | `PodInfo[]` | 네임스페이스 내 Pod 목록 |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/pods/{name}` | `204` | Pod 삭제 |
| `GET` | `/{cluster_id}/namespaces/{namespace}/pods/{name}/log` | `PodLogResponse` | Pod 로그 조회 |

**로그 쿼리 파라미터**

| 쿼리 | 타입 | 기본 | 설명 |
|------|------|------|------|
| `container` | string | — | 다중 컨테이너 Pod 에서 대상 컨테이너 지정 |
| `tail_lines` | int | `200` | 마지막 N줄. 범위 `1~10000` |

`PodInfo` 주요 필드: `name`, `namespace`, `phase`, `ready`, `restarts`, `node`, `pod_ip`, `containers[]`(`name`/`image`/`ready`/`restart_count`/`state`), `labels`, `created_at`.

---

## Deployment / ReplicaSet

| 메서드 | 경로 | 응답 | 설명 |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/deployments` | `DeploymentInfo[]` | Deployment 목록 |
| `GET` | `/{cluster_id}/namespaces/{namespace}/replicasets` | `ReplicaSetInfo[]` | ReplicaSet 목록 |
| `POST` | `/{cluster_id}/namespaces/{namespace}/deployments/{name}/restart` | `DeploymentInfo` | 롤링 재시작 (rollout restart) |
| `PATCH` | `/{cluster_id}/namespaces/{namespace}/deployments/{name}/scale` | `DeploymentInfo` | 레플리카 수 조정 |

**scale 요청 본문** `ScaleDeploymentRequest`

```json
{ "replicas": 3 }
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `replicas` | int | 목표 레플리카 수. 범위 `0~100` |

`DeploymentInfo` 주요 필드: `name`, `namespace`, `replicas`, `available`, `ready`, `updated`, `strategy`, `selector`, `images[]`, `created_at`.

---

## Service

| 메서드 | 경로 | 응답 | 설명 |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/services` | `ServiceInfo[]` | Service 목록 |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/services/{name}` | `204` | Service 삭제 |

`ServiceInfo` 주요 필드: `name`, `namespace`, `type`, `cluster_ip`, `external_ips[]`, `ports[]`(`port`/`target_port`/`node_port`/`protocol`), `selector`, `created_at`.

---

## ConfigMap

목록은 쿼리 파라미터로 네임스페이스를 받고, 상세/변경은 경로에 네임스페이스를 포함합니다.

| 메서드 | 경로 | 응답 | 설명 |
|--------|------|------|------|
| `GET` | `/{cluster_id}/configmaps?namespace={ns}` | `ConfigMapInfo[]` | ConfigMap 목록 (기본 `namespace=default`) |
| `GET` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `ConfigMapInfo` | 단건 조회 |
| `POST` | `/{cluster_id}/namespaces/{namespace}/configmaps` | `201` `ConfigMapInfo` | 생성 |
| `PUT` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `ConfigMapInfo` | 갱신 |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `204` | 삭제 |

**생성 요청 본문** `ConfigMapCreateRequest`

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | ConfigMap 이름 |
| `data` | object | 키-값 문자열 맵 |
| `labels` / `annotations` | object? | 메타데이터 |

`PUT` 은 `ConfigMapWriteRequest`(`data`, `labels`, `annotations`, `binary_data`)를 받습니다.

---

## Secret

> **보안 주의**
> - `SecretInfo.data` 는 K8s 원본 그대로 **base64 인코딩된 값**으로 반환됩니다(평문 복호화 아님).
> - 생성/갱신 요청의 `data` 는 **평문**으로 받아 백엔드가 인코딩합니다.
> - 조작 audit 로그에는 이름/namespace 만 기록하고 **Secret 값은 남기지 않습니다.**

| 메서드 | 경로 | 응답 | 설명 |
|--------|------|------|------|
| `GET` | `/{cluster_id}/secrets?namespace={ns}` | `SecretInfo[]` | Secret 목록 (기본 `namespace=default`) |
| `GET` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `SecretInfo` | 단건 조회 |
| `POST` | `/{cluster_id}/namespaces/{namespace}/secrets` | `201` `SecretInfo` | 생성 |
| `PUT` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `SecretInfo` | 갱신 |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `204` | 삭제 |

**생성 요청 본문** `SecretCreateRequest`

| 필드 | 타입 | 기본 | 설명 |
|------|------|------|------|
| `name` | string | — | Secret 이름 |
| `type` | string | `Opaque` | Secret 타입 |
| `data` | object | — | 키-값 (**평문**) |
| `labels` / `annotations` | object? | — | 메타데이터 |

`PUT` 은 `SecretWriteRequest`(`type`, `data`, `labels`, `annotations`)를 받습니다.

---

## Cloud Shell

브라우저 터미널에서 클러스터에 `kubectl`/`sh` 를 실행하는 exec 채널입니다. 짧은 수명의 티켓을 발급받아 WebSocket 인증에 사용합니다.

### `POST /{cluster_id}/shell-ticket`

WebSocket 연결용 일회용 티켓을 발급합니다. 클러스터가 `ACTIVE` 상태가 아니면 `409`.

**응답 `201`**

```json
{ "ticket": "<url-safe-token>", "expires_in": 30 }
```

- 티켓 TTL: **30초** (Redis 저장, 1회 사용 후 소멸).
- 발급은 audit 로깅됩니다.

### `WS /{cluster_id}/shell?ticket={ticket}`

K8s exec 프로토콜(`v4.channel.k8s.io`)을 프록시하는 WebSocket 엔드포인트입니다.

- 쿼리 `ticket` 으로 인증 — 유효하지 않으면 연결 종료(`4401`), 클러스터 불일치 시 `4403`.
- 사용자별 shell Pod 세션을 보장하고, 유휴 타임아웃(idle timeout) 경과 시 자동 종료(`4408`).
- 연결 종료 시 shell Pod 를 best-effort 로 정리합니다.

---

## 오류 코드

| 코드 | 설명 |
|------|------|
| `404` | 클러스터를 찾을 수 없음(미존재 또는 타 프로젝트 소유) |
| `409` | (shell-ticket) 클러스터가 `ACTIVE` 상태 아님 |
| `422` | 요청 본문 검증 실패 (예: `replicas` 범위 초과) |
