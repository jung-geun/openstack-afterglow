## Implementation Tasks

### Phase 0 — 의존성 정합성 (go/no-go)

- [x] 의존성 공동 resolution 스파이크 = GO (하드핀 유지, 핀 이동 불필요): litellm 1.83.0 / langgraph 1.2.2 / langchain-core 1.4.9 / langchain-mcp-adapters 0.3.0 / mcp 1.12.4

### Phase 1 — 백엔드 코어 (litellm · SSE · 영속화 · 크레딧)

- [x] `pyproject.toml` litellm==1.83.0 추가 + `uv sync`(32 패키지 설치, import 검증)
- [x] `config.py` `[chat]` 재구성(default_model/credit_per_usd/quota_default/stream_enabled) + `generate_k8s.py` + `afterglow.conf.example` 동기화
- [x] `migrations/026_chat_builtin.sql` + `models/db.py`(`models/chat_db.py`) ORM(llm_providers/llm_models/chat_conversations/chat_messages/chat_usage_logs/user_wallets) — import sanity 검증
- [x] `k3s_crypto.py` `_DOMAIN_LLM_PROVIDER_KEY` + encrypt/decrypt 헬퍼 — `tests/test_chat_crypto.py` 6 passed
- [x] `services/chat/provider_store.py`(암호화 저장/해석 resolve_model) + 관리자 CRUD `api/chat/models.py`(require_admin, 키 마스킹) + main.py 마운트 + 감사맵(llm_provider/llm_model) — `tests/test_chat_admin_providers.py` 등 25 passed
- [x] `services/chat/litellm_client.py`(lazy import, 스트리밍 usage 계측 `include_usage`+`token_counter` 폴백, `cost_per_token`) — `tests/test_chat_litellm_client.py` 9 passed
- [ ] `chat_engine` 인터페이스 + Phase1 직접 litellm 구현
- [x] `services/chat/credit.py`(fail-closed precheck, 원자적 차감 UPDATE, 월 lazy 리셋, apply_usage 원장 기록) — `tests/test_chat_credit.py` 7 passed. (model_name 화이트리스트·입력 상한은 completions 엔드포인트에서 적용)
- [x] `api/chat/conversations.py`(+메시지 목록) + `conversation_store.py`(project_id/user_id 소유권 403/404) — `tests/test_chat_conversations.py`
- [x] `chat_engine`(engine.py) + `api/chat/completions.py`(precheck→소유권→resolve_model 화이트리스트→SSE token/error/done→finally 과금, 입력 상한) — `tests/test_chat_completions.py`(쿼터 402·소유권 403·화이트리스트 400·스트리밍 raw_cost>0)
- [x] `main.py` 라우터 마운트(admin/conversations/completions) + `_AUDIT_PREFIX_MAP`(llm_provider/llm_model/chat_conversation) + mutation-invalidate 커버리지 예외 등록
- [x] `tests/test_chat_*.py`: 프로바이더 CRUD·소유권 403·쿼터 402·스트리밍 credited_cost>0·오류시 미과금·화이트리스트·암호화 왕복 — **59 chat 단위/라우터 테스트 통과, 전체 백엔드 회귀 0**
- [x] `tests/test_chat_db_integration.py`(`@pytest.mark.db`): 마이그레이션/ORM/resolve_model JOIN+복호화(v3:)/원자적 used_quota UPDATE+원장/쿼터 차단 라운드트립 — 로컬 skip, **CI test-backend-db 에서 실행**
- [x] 과금 정합성 수정: 모델 하드 실패(error 이벤트) 시 과금·done 스킵(실패 요청 과금 방지)

### Phase 2 — LangGraph + MCP 툴

- [ ] `langgraph`/`langchain-core`/`langchain-mcp-adapters`/`mcp` + `langgraph-checkpoint-postgres` 의존성 추가
- [ ] 전용 Postgres 체크포인터 인프라(`chat_checkpointer_postgres_url` 설정 게이팅, 미설정 시 MemorySaver fallback) — 설정 동기화 + generate_k8s
- [ ] `services/chat/graph.py` StateGraph(load_memory→agent→tools→persist) + `AsyncPostgresSaver`/MemorySaver + 메모리 truncation (전사는 MySQL chat_messages)
- [ ] `services/chat/mcp_registry.py`(관리자 화이트리스트, SSRF 차단, graceful)
- [ ] `services/chat/tools.py`(project_id 컨텍스트 강제 주입, 소유권 재검증, 화이트리스트, shlex_quote)
- [ ] `completions` graph 경로 전환(astream_events) + 멀티스텝 사용량 합산
- [ ] tests: 툴 바인딩·테넌트 격리·인젝션 방어·MCP 로드 실패 graceful·멀티스텝 과금

### Phase 3 — 과금/관리자/외부 키 + LibreChat 제거 + 프론트

- [ ] `migrations/027_chat_external_keys.sql` + `services/chat/apikey.py` + `api/chat/keys.py`(소유권)
- [ ] `get_api_key_principal`(매 요청 is_active, compare_digest) + OpenAI 호환 `POST /api/v1/chat/completions` + Redis RPM/RPD
- [ ] 사용량 통계 API(SUM by project/user/time) + 모델 단가 API + `api/chat/wallet.py`
- [ ] 월 쿼터 리셋 스케줄러(apscheduler/startup 루프, 멱등) + SaaS 필드(margin/balance)
- [ ] LibreChat 제거: `librechat_mongo.py` 삭제, `usage.py` 신규 스키마 교체, config 키 제거(동기화 3곳), `site_branding.py` 조건 수정, `service_chat_enabled` 재정의
- [ ] 프론트: `LibreChatEmbed.svelte` 제거 → 채팅 UI, chat API 클라이언트, 외부 키/관리자 화면, usage-report·mockup·gated-surfaces 갱신
- [ ] tests: 외부 키 인증·폐기·레이트리밋·통계·월 리셋

### 횡단/검증

- [ ] 커밋 전 `npm run test:all` && `npm run lint:backend` (둘 다 0)
- [ ] 감사 매핑·소유권·shlex_quote·compare_digest·시크릿 암호화·로그 위생 체크리스트
- [ ] `dev` 브랜치 작업, 완료 시 `/opsx:archive`
