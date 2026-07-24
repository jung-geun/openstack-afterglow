---
title: VPN (VPNaaS)
parent: API 레퍼런스
nav_order: 61
---

# VPN (VPNaaS) API

WireGuard 기반 VPN 게이트웨이를 프로비저닝하고, 서버마다 클라이언트(peer)를 발급합니다. 서버는 OpenStack VM으로 부팅되며, 그 위의 **VPN 에이전트**가 별도 콜백 경로로 서버 상태를 보고하고 desired-state(peer 목록)를 폴링합니다.

> **선택 서비스** — `config.toml [services]` 에서 활성화하고, `afterglow.conf [vpn]` 의 `provider_network_id` 와 `image_id` 를 설정해야 합니다.
> 미설정 시 서버 생성 요청은 `503` 을 반환합니다. DB(SQLAlchemy)가 필요하며, DB 미가용 시 `503`.

---

## 계층 구조

```
VPN 서버 (VM, WireGuard 게이트웨이)
  └─ 클라이언트 (peer) — .conf 다운로드로 접속
```

- **서버**와 **클라이언트** 관리 엔드포인트는 사용자 JWT(`get_token_info`)로 인증하며, `project_id` 소유권을 검증합니다. 소유하지 않았거나 존재하지 않는 서버는 정보 노출 방지를 위해 모두 `404` 로 응답합니다.
- **에이전트 콜백** 엔드포인트(`/agent/*`)는 사용자 JWT가 아니라 **에이전트 전용 Bearer 토큰**으로 인증합니다. 아래 [3. 에이전트 콜백](#3-에이전트-콜백-vm-에이전트-전용) 참조.

---

## 인증 헤더 (사용자 API)

| 헤더 | 설명 |
|------|------|
| `Authorization: Bearer <JWT>` | 사용자 세션 JWT |

---

## 목차

1. [VPN 서버](#1-vpn-서버)
2. [VPN 클라이언트 (peer)](#2-vpn-클라이언트-peer)
3. [에이전트 콜백 (VM 에이전트 전용)](#3-에이전트-콜백-vm-에이전트-전용)

---

## 1. VPN 서버

기본 경로: `/api/v1/vpn/servers`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/v1/vpn/servers` | 서버 프로비저닝 (201, `CREATING` 즉시 응답) |
| `GET` | `/api/v1/vpn/servers` | 서버 목록 |
| `GET` | `/api/v1/vpn/servers/{server_id}` | 서버 상세 |
| `DELETE` | `/api/v1/vpn/servers/{server_id}` | 서버 삭제 (202, 백그라운드 `DELETING`) |

### POST /api/v1/vpn/servers

VPN 서버 VM 프로비저닝을 요청합니다. DB에 `CREATING` 레코드를 만들고 **즉시 응답**한 뒤, 백그라운드에서 VM을 부팅합니다. 서버가 부팅되고 에이전트가 register 를 호출하면 상태가 `ACTIVE` 로 전이됩니다.

**요청 본문**

```json
{ "name": "string (선택)" }
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 아니오 | 서버 이름. 비우면 `vpn-<8자리>` 자동 생성. 영문/숫자로 시작, 영문·숫자·하이픈·언더스코어만 (최대 63자) |

**응답 (201 Created)** — `VpnServerInfo`. `listen_port`·`tunnel_cidr` 은 `afterglow.conf [vpn]` 기본값에서 설정됩니다. `server_public_key`·`endpoint_ip` 는 에이전트 register 이후 채워집니다.

### GET /api/v1/vpn/servers/{server_id}

서버 상세를 반환합니다. DB 레코드에 Redis의 에이전트 최신 보고(마지막 보고 시각 `last_status_reported_at`, `peer_count`)를 병합합니다.

### DELETE /api/v1/vpn/servers/{server_id}

서버를 삭제합니다. 백그라운드에서 VM·리소스를 정리하며 즉시 `DELETING` 을 반환합니다.

**응답**: `202 Accepted` — `{ "ok": true, "status": "DELETING" }`

---

## 2. VPN 클라이언트 (peer)

기본 경로: `/api/v1/vpn/servers/{server_id}/clients`

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `.../{server_id}/clients` | 클라이언트 발급 (201) |
| `GET` | `.../{server_id}/clients` | 클라이언트 목록 |
| `PATCH` | `.../{server_id}/clients/{client_id}` | 클라이언트 수정 (이름/활성화) |
| `DELETE` | `.../{server_id}/clients/{client_id}` | 클라이언트 삭제 (204, soft delete) |
| `GET` | `.../{server_id}/clients/{client_id}/config` | **`.conf` 다운로드** |

### POST /api/v1/vpn/servers/{server_id}/clients

새 클라이언트(peer)를 발급합니다. 서버 측에서 WireGuard 키쌍을 생성하고, private key는 **AES-GCM으로 암호화 저장**하며, 터널 CIDR에서 다음 IP를 자동 할당합니다.

- 서버가 `ACTIVE` 가 아니거나(에이전트 register 대기 중) 서버 공개키가 아직 없으면 `409`.
- 이름 중복·터널 IP 충돌 시 `409`.

**요청 본문**

```json
{
  "name": "string (필수)",
  "allowed_ips": ["10.8.0.0/24"],
  "dns": "1.1.1.1"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | 예 | 클라이언트 이름 (영문/숫자 시작, 최대 63자) |
| `allowed_ips` | string[] | 아니오 | 이 peer 로 라우팅할 CIDR 목록 (최대 20개, 미지정 시 서버 터널 CIDR). 각 항목은 유효한 CIDR 이어야 함 |
| `dns` | string | 아니오 | 클라이언트 DNS (호스트네임/IP, 콤마 구분 최대 2개) |

**응답 (201 Created)** — `VpnClientCreateResponse`. 이 응답에는 평문 `tunnel_conf`(WireGuard `.conf` 내용)가 포함됩니다.

### GET /api/v1/vpn/servers/{server_id}/clients/{client_id}/config

클라이언트 `.conf` 파일을 다운로드합니다. **매 호출마다** 저장된 private key를 복호화해 `.conf` 를 재렌더합니다(k3s kubeconfig 다운로드 패턴과 동일). 따라서 발급 직후뿐 아니라 언제든 동일한 설정을 다시 받을 수 있습니다.

- 서버 공개키/엔드포인트 IP가 아직 준비되지 않았으면 `409`.
- private key 복호화 실패 시 `500`.

**응답**: `200 OK` — `text/plain`, `Content-Disposition: attachment; filename="<name>.conf"`

### PATCH /api/v1/vpn/servers/{server_id}/clients/{client_id}

클라이언트 이름을 바꾸거나 활성/비활성(`enabled`)을 토글합니다. 비활성화하면 에이전트 desired-state에서 제외됩니다.

**요청 본문**

```json
{ "name": "string (선택)", "enabled": false }
```

### DELETE /api/v1/vpn/servers/{server_id}/clients/{client_id}

클라이언트를 소프트 삭제합니다.

**응답**: `204 No Content`

---

## 3. 에이전트 콜백 (VM 에이전트 전용)

기본 경로: `/api/v1/vpn/servers/{server_id}/agent`

> 이 엔드포인트들은 **사용자가 직접 호출하지 않습니다.** VPN 서버 VM 위에서 동작하는 에이전트가 호출하는 머신 대면 경로입니다.

### 인증

- 사용자 JWT가 아니라 **에이전트 전용 Bearer 토큰**(`Authorization: Bearer <token>`)으로 인증합니다.
- 토큰은 검증 후 요청 경로의 `server_id` 에 **바인딩**되어 있는지 확인합니다. 토큰이 무효면 `401`, 다른 서버에 귀속된 토큰이면 `403` (fail-closed).
- 사용자 JWT를 쓰지 않으므로 활동 감사 미들웨어는 이 경로를 자동으로 건너뜁니다.
- 이 패턴은 `compute/instance_health.py` 의 Bearer 추출 + rate-limit + fail-closed 방식을 그대로 미러링합니다.

### 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `.../{server_id}/agent/register` | 부팅 후 서버 공개키 보고 (204, 30/분) |
| `GET` | `.../{server_id}/agent/desired-state` | peer 목록·설정 폴링 (120/분) |
| `POST` | `.../{server_id}/agent/status` | `wg show` 상태 보고 (204, 60/분) |

### POST /agent/register

에이전트가 부팅 후 자신의 WireGuard 서버 공개키를 보고합니다. `CREATING`/`PROVISIONING`/`ACTIVE` 상태의 서버를 `ACTIVE` 로 전이시키며, 재부팅 시 반복 호출로 공개키를 갱신할 수 있습니다.

**요청 본문**: `{ "public_key": "<base64 WG key>", "listen_port_confirm": 51820 }`

### GET /agent/desired-state

에이전트가 주기적으로 폴링하는 목표 상태입니다. 활성 클라이언트의 `public_key`·`preshared_key`(복호화)·`tunnel_ip`·`enabled` 와 `listen_port`·`tunnel_cidr` 을 반환합니다.

### POST /agent/status

에이전트가 `wg show` 결과(peer별 마지막 핸드셰이크·송수신 바이트)를 보고합니다. 서버는 이를 Redis에 캐시(TTL 5분)하고, 사용자 대면 서버/클라이언트 조회 응답에 온라인 상태로 병합합니다.

**요청 본문**: `{ "peers": [ { "public_key": "...", "last_handshake_at": "...", "rx_bytes": 0, "tx_bytes": 0 } ], "reported_at": "..." }`
