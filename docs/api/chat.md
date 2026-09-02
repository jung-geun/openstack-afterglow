---
title: 채팅 (Chat)
parent: API 레퍼런스
nav_order: 64
---

# 채팅 (Chat) API (Lumen AI API 프록시)

> 태그: `chat`
> 기본 경로: `/api/v1/chat`

Afterglow 백엔드는 독자적인 AI 모델 실행 엔진, LiteLLM 라우팅, LangGraph/LangChain 에이전트 런타임 및 공급자 API 키를 포함하지 않으며, 외부 **Lumen AI API** 서비스의 인증된 **BFF(Backend-For-Frontend) 프록시** 역할을 수행합니다.

직접적인 OpenAI / Anthropic 호환 API 호스팅은 Lumen 서비스가 전담합니다.

> **활성화 조건:** `afterglow.conf [services] chat = true` 및 `[services] lumen_internal_url` (또는 Keystone 서비스 카탈로그).
> 비활성화 상태에서는 `/api/v1/chat` 라우터가 마운트되지 않습니다.

---

## 인증 방식

### 1. 사용자 세션 인증 (Browser BFF Routes)
웹 프론트엔드의 모든 `/api/v1/chat/*` 엔드포인트 요청은 사용자의 세션 토큰 인증이 필수입니다.

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <access_token>` (로그인 응답의 access JWT) |
| `X-Project-Id` | (선택) 프로젝트 UUID — 생략 시 토큰의 기본 프로젝트 사용 |

### 2. 쿠키 기반 인증 콜백 (OAuth Callback)
`GET /api/v1/chat/mcp-oauth/callback` 경로의 브라우저 리다이렉트 콜백은 Bearer 토큰 없이 상태 쿠키(`Cookie`)를 보존하여 Lumen 상위 경로로 전달합니다.

### 3. 워크로드 인증 (Delegated MCP Control-Plane Bridge)
Lumen 워크로드가 Afterglow의 MCP 제어면을 호출하는 `/api/v1/mcp/lumen/*` 경로는 워크로드 전용 공유 비밀문자열로 인증합니다.

| 헤더 | 설명 |
|------|------|
| `Authorization` | `Bearer <LUMEN_MCP_SERVICE_TOKEN>` |

---

## 주요 프록시 엔드포인트

Afterglow 백엔드는 모든 `/api/v1/chat/{path}` 요청을 내부 Lumen 서비스 URL의 `/v1/{path}` 경로로 투명하게 위임하며, SSE(Server-Sent Events) 스트리밍 응답의 비버퍼링 전달을 보장합니다.

| 메서드 · 경로 | 상위 위임 경로 | 설명 |
|--------------|----------------|------|
| `GET /api/v1/chat/models` | `/v1/chat/models` | 사용 가능한 LLM 모델 목록 조회 |
| `GET /api/v1/chat/conversations` | `/v1/conversations` | 대화 목록 조회 |
| `POST /api/v1/chat/conversations` | `/v1/conversations` | 신규 대화 생성 |
| `POST /api/v1/chat/conversations/{id}/completions` | `/v1/conversations/{id}/completions` | 실행을 접수하고 `202` run descriptor 반환; 이후 events URL로 SSE 구독 |
| `GET /api/v1/chat/runs/{run_id}/events` | `/v1/runs/{run_id}/events` | 실시간 실행 이벤트 스트림 (SSE 스트리밍) |
| `POST /api/v1/chat/runs/{run_id}/cancel` | `/v1/runs/{run_id}/cancel` | 실행 중인 에이전트 중단 |
| `POST /api/v1/chat/runs/{run_id}/approvals/{call_id}` | `/v1/runs/{run_id}/approvals/{call_id}` | 사용자 승인/거절 상태 제출 |
| `GET /api/v1/chat/usage` | `/v1/usage` | 사용자 본인의 토큰 및 크레딧 사용량 조회 |
| `GET /api/v1/chat/mcp-oauth/callback` | `/v1/mcp-oauth/callback` | MCP OAuth 브라우저 콜백 전달 |

---

## 위임 MCP 제어면 브릿지 (`/api/v1/mcp/lumen`)

Lumen 서비스가 Afterglow 사용자의 MCP 도구 권한 상태를 검증하고 도구를 실행하기 위해 호출하는 제어면 API입니다.

| 메서드 · 경로 | 설명 |
|--------------|------|
| `POST /api/v1/mcp/lumen/snapshot` | 사용자/프로젝트 단위 MCP 승인 불투명 스냅샷 조회 |
| `POST /api/v1/mcp/lumen/preview` | 변개(Mutation) 도구 실행 전 제어면 사전 검증 |
| `POST /api/v1/mcp/lumen/execute` | 격리된 MCP 도구 단일 실행 및 원장(Ledger) 기록 |
