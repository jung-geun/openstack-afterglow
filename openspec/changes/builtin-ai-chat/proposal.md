## Why

현재 대시보드의 AI 채팅은 외부 LibreChat 인스턴스(`chat.dmslab.re.kr`)를 iframe으로 임베드(`frontend/src/lib/components/LibreChatEmbed.svelte`)하고, 백엔드는 LibreChat MongoDB를 읽기 전용으로 조회해 사용량만 미러링(`backend/app/api/chat/usage.py` + `backend/app/services/librechat_mongo.py`)한다. iframe 임베드는 CORS·SameSite 쿠키·IDP(Keystone/GitLab federation) 계정 연동 마찰이 크고, 사용량 제한·멀티테넌시·크레딧 과금 같은 플랫폼 핵심 통제권을 외부 시스템에 의존한다. 이를 걷어내고 대시보드에 결합도 높은 빌트인 AI 채팅으로 전환한다.

## What Changes

- **LibreChat 임베드 즉시 대체**: `service_chat_enabled` 플래그를 "빌트인 채팅"으로 재정의. `LibreChatEmbed.svelte`·`librechat_mongo.py`·`librechat_mongo_url`/`librechat_base_url` 제거.
- **빌트인 채팅 백엔드**: `litellm`(in-process SDK) 라우팅, SSE 스트리밍, `LangGraph` StateGraph 오케스트레이션 + `langchain-mcp-adapters` MCP 툴, 대화/메시지/사용량/지갑 상태를 자체 MySQL(`models/db.py` + 순번 마이그레이션 `026`/`027`)에 저장(원안의 PostgreSQL/PostgresSaver는 이 코드베이스가 MySQL이므로 미적용).
- **과금**: 모델별 가중 비용 크레딧(`litellm.completion_cost` + 스트리밍 usage 계측) + 월간 쿼터 상한. 상용 전환 대비 마진 배수·잔액 필드 선반영.
- **외부 API 키**: 발급/해싱(sha256 + `hmac.compare_digest`)/폐기 + OpenAI 호환 엔드포인트(`POST /api/v1/chat/completions`) + Redis 레이트리밋.
- **관리자/사용자 화면**: 프로바이더/모델 CRUD(암호화 키는 `k3s_crypto` 확장), 사용량 통계·모델 단가 화면, 실제 채팅 UI, 외부 키 관리.

## Capabilities

### New Capabilities

- 빌트인 AI 채팅(SSE 스트리밍 + LangGraph/MCP 툴 오케스트레이션, 테넌트 스코프 격리)
- 모델별 가중 크레딧 + 월 쿼터 사용량 제어 및 원장(`chat_usage_logs`)
- 외부 프로그램용 API 키 발급 + OpenAI 호환 엔드포인트
- 관리자 프로바이더/모델 동적 설정(암호화 저장) 및 사용량·단가 대시보드

### Modified Capabilities

- `service_chat_enabled` 의미(임베드 → 빌트인) 및 `/api/v1/chat/*` API 표면
- `frontend .../dashboard/chat` 페이지(임베드 → 실제 채팅 UI), `usage-report`의 사용량 소비 스키마

## Impact

- 백엔드: 신규 `app/api/chat/*`(conversations/messages/completions/models/wallet/keys), `app/services/chat/*`, `models/db.py` ORM 7개 테이블 + 마이그레이션 `026`/`027`, `k3s_crypto` 도메인 추가, `main.py` 라우터 마운트 + `_AUDIT_PREFIX_MAP` 등록, `config.py`/`generate_k8s.py`/`afterglow.conf.example` 설정 동기화.
- 의존성: `litellm`·`langgraph`·`langchain-core`·`langchain-mcp-adapters`·`mcp` 추가(정합성 스파이크 완료 — 기존 하드핀 `pydantic==2.9.2`/`fastapi==0.125.0` 유지, 핀 이동 불필요). `motor`는 LibreChat 제거 후 사용처 소멸 시 제거 검토.
- 프론트: `LibreChatEmbed.svelte` 제거, `dashboard/chat` 채팅 UI, chat API 클라이언트, 관리자/키 화면, `mockup/transport.ts`·gated-surfaces 테스트 갱신.
- 테스트: 엔드포인트별 pytest(의무) + 테넌트 격리·인젝션·크레딧 회귀. 기존 baked 레거시 계약·감사 미들웨어는 유지.

## Capability Platform Expansion

The original built-in chat delivery is now expanded into a durable capability platform. The implementation source of truth is `local://chat-capability-platform-plan.md`; this proposal records the OpenSpec ledger scope.

- Replace text-only request, stream, storage, and pricing shapes with canonical typed message parts, run events, feature options, and component usage contracts shared by FastAPI, LangGraph, workers, storage, and the Svelte client.
- Keep MySQL as the encrypted conversation and financial source of truth. Add a durable MySQL run journal, assets, jobs, derivations, and memory outbox; use separately configured PostgreSQL databases only for encrypted LangGraph checkpoints and content-free pgvector search indexes.
- Change completion creation to an idempotent `202` descriptor protocol owned by a separate chat worker. SSE replays the durable journal and never treats a disconnect as cancellation; persisted `run.stage.changed` events expose the current execution stage and its start time across reconnects.
- Add capability- and immutable-pricing-gated structured output, function calling with approval, native/managed search and fetch, advisor calls, secure multimodal assets, semantic memory, MCP streamable HTTP, and provider-managed sandbox support.
- Migrate the chat UI to typed create-then-follow run ownership, persisted temporary threads, capability-aware composition, typed part rendering, accessibility, and deterministic mock fixtures.
- Retain the existing unimplemented external OpenAI-compatible API-key work as a separate ledger item; it is not combined with this chat-page capability implementation.
