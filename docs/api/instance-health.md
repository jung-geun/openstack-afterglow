---
title: 인스턴스 헬스 (Instance Health)
parent: API 레퍼런스
nav_order: 34
---

# 인스턴스 헬스 (Instance Health) API

> 태그: `instance-health`
> 기본 경로: `/api/v1/instances`

Union Mount VM의 OverlayFS/파일 스토리지 헬스체크와 CephX 자격 증명 회전을 처리합니다. 일부 엔드포인트는 **VM 내부 에이전트가 Bearer 토큰으로 호출**하는 경로입니다(사용자 UI 인증과 별개).

---

## 인증 방식

| 인증 | 사용 경로 | 설명 |
|------|-----------|------|
| Bearer 토큰 | `POST /{id}/health/report`, `POST /{id}/credentials/rotate-cephx` | VM 생성 시 cloud-init user-data에 주입된 헬스 리포트 토큰. `Authorization: Bearer <token>` 헤더 필요. 토큰은 해당 인스턴스에 귀속됨 |
| `Authorization: Bearer` (+ `X-Project-Id`) | `GET /{id}/health`, `GET /health` | 일반 사용자 인증(JWT) |

> **토큰 절대 만료 7일.** 헬스 리포트 토큰은 발급 시점 기준 7일 후 절대 만료됩니다(sliding 갱신 없음). VM userdata가 노출되어도 7일 후 CephX 회전 권한이 무효화되며, 7일 이상 살아있는 인스턴스는 게스트 내 헬스 스크립트의 재발급 흐름으로 새 토큰을 받습니다. 헬스 결과 데이터는 Redis에 30분 TTL로 저장됩니다.

---

## 엔드포인트 목록

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `POST` | `/api/v1/instances/{instance_id}/health/report` | Bearer | VM 헬스 리포트 수신 (30/분) &sup1; |
| `GET` | `/api/v1/instances/{instance_id}/health` | 사용자 | 인스턴스 헬스 결과 조회 |
| `POST` | `/api/v1/instances/{instance_id}/credentials/rotate-cephx` | Bearer | CephX 키 회전, 새 자격 증명 반환 (10/분) &sup1; |
| `GET` | `/api/v1/instances/health` | 사용자 | 프로젝트 내 인스턴스 헬스 일괄 조회 |

&sup1; 레거시 `/api/instances/...` 경로로도 유효합니다(cloud-init baked — 기존 VM은 재bake 없이 이 경로를 호출하므로 dual-mount 유지). 신규 통합은 `/api/v1` 경로를 사용하세요.

---

## POST /api/v1/instances/{instance_id}/health/report

VM 내부 헬스체크 스크립트가 주기적으로 상태를 보고합니다. **속도 제한: 30회/분.**

**인증**: `Authorization: Bearer <report_token>`. 토큰이 유효하지 않거나(`401`) 해당 인스턴스에 귀속되지 않으면(`403`) 거부됩니다.

**요청 본문** (`InstanceHealthReport`)

| 필드 | 타입 | 설명 |
|------|------|------|
| `overlay_mounted` | boolean | OverlayFS 마운트 여부 |
| `upper_used_bytes` / `upper_total_bytes` | integer | upper 볼륨 사용/전체 바이트 |
| `upper_usage_pct` | float | upper 사용률(%) |
| `shares` | array | `{name, proto("CEPHFS"\|"NFS"\|"NONE"), mounted, status("ok"\|"unreachable"\|"timeout")}` |
| `kernel` | string | 커널 버전 |
| `uptime_seconds` | float | 가동 시간(초) |
| `reported_at` | string | 보고 시각 (ISO 8601) |

**응답**: `204 No Content`

---

## GET /api/v1/instances/{instance_id}/health

인스턴스 헬스 결과를 조회합니다. Nova 메타데이터의 `union_health_id`로 Redis를 조회하며, 조회 실패 시 `instance_id`를 fallback 키로 사용합니다.

**응답 (200 OK)** — `InstanceHealth`

| 필드 | 타입 | 설명 |
|------|------|------|
| `instance_id` | string | 인스턴스 식별자 |
| `status` | string | `healthy` \| `warning` \| `error` \| `stale` \| `unknown` |
| `warnings` | array[string] | 경고 목록 |
| `overlay_mounted` | boolean | OverlayFS 마운트 여부 |
| `upper_used_bytes` / `upper_total_bytes` / `upper_usage_pct` | number | upper 볼륨 사용량 |
| `shares` | array | 리포트의 share 상태 목록 |
| `kernel` / `uptime_seconds` | string / float | 커널·가동 시간 |
| `reported_at` / `checked_at` | string \| null | 보고/판정 시각 |

**오류**: `404 Not Found` — 헬스 데이터 없음(아직 미보고 또는 30분 TTL 만료)

---

## POST /api/v1/instances/{instance_id}/credentials/rotate-cephx

VM CephX 키를 회전하고 새 자격 증명을 반환합니다. 게스트의 `union-rotate-key.timer`가 주기적으로 호출합니다. **속도 제한: 10회/분.**

**인증**: `Authorization: Bearer <report_token>`. 토큰의 `cephx_access_id`/`cephx_share_id`로 대상 access rule을 식별합니다.

**응답 (200 OK)**

```json
{
  "cephx_user": "union-rw-my-vm",
  "cephx_key": "AQ...==",
  "new_access_id": "uuid-string",
  "monitors": "10.0.0.1:6789,10.0.0.2:6789"
}
```

**오류**
- `401 Unauthorized` — Bearer 토큰 누락/무효
- `403 Forbidden` — 토큰이 해당 인스턴스에 귀속되지 않음
- `422 Unprocessable Entity` — 토큰에 `cephx_access_id`/`cephx_share_id` 누락
- `404 Not Found` — 대상 access rule 없음
- `502 Bad Gateway` — Manila CephX 키 회전 실패
- `503 Service Unavailable` — CephX 키 회전이 비활성화됨(`union_cephx_rotate_hours=0`)

---

## GET /api/v1/instances/health

프로젝트 내 인스턴스의 헬스 결과를 일괄 조회합니다(Redis 보고 데이터 기반). 오류가 발생해도 빈 배열을 반환합니다.

**응답 (200 OK)** — `InstanceHealth` 배열
