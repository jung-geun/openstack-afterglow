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

- [x] 의존성: `langgraph==1.2.2`/`langchain-core==1.4.9`/`langgraph-checkpoint-postgres==3.1.0`/`psycopg[binary]==3.3.4` 추가·검증 (커밋 `f03ad53a`).
- [!] **외부 MCP 블로커(근본원인 규명)**: `langchain-mcp-adapters 0.3.0`은 모던 `mcp 1.28.1` 필요 → mcp 1.28.1이 하드핀 3개와 충돌(`pydantic>=2.11` vs 2.9.2, `uvicorn>=0.31.1` vs 0.30.6, `httpx>=0.28` vs 0.27.2). **외부 MCP = 백엔드 전역 pydantic/uvicorn/httpx 이동 강제 → pie_root 승인·전체 재검증 필요(미결정).** litellm은 mcp 무관. **대안**: 내부 플랫폼 툴(tools.py)은 MCP 라이브러리 불요 → 자체 tool 루프로 unblocked.
- [x] Postgres 체크포인터 **설정 동기화**: `config.py` `chat_checkpointer_postgres_url`(secret) + `generate_k8s.py` render_secret + `afterglow.conf.example` — 설정 검증 OK. (checkpointer.py 선택 로직은 graph.py와 함께 구현)
- [x] `services/chat/graph.py` 에이전트 루프 — litellm 커스텀 노드 + `get_stream_writer()`/`stream_mode="custom"` 토큰 스트리밍 + **tool_call 델타 누적 → 테넌트 안전 실행 → 최종 답변 스트리밍 + 멀티스텝 usage 합산**. `engine.stream`이 위임. **잔여**: 체크포인터 wiring(MemorySaver/AsyncPostgresSaver), 메모리 truncation. (대화 전사는 이미 MySQL chat_messages 로드)
- [x] `services/chat/tools.py`(내부 플랫폼 툴) — **project_id/user_id 컨텍스트 강제 주입(LLM 인자 무시)**, 소유권 재검증(IDOR), 화이트리스트, 예외 미전파. 스타터 툴: list_my_conversations / get_conversation_detail. `tools()` OpenAI 스키마 + `execute_tool` 디스패처.
- [x] `completions` graph 경로(내부 툴 루프) + 멀티스텝 usage 합산 + `tool_call` SSE 중계. 사용자용 `GET /api/v1/chat/models` 추가. 프론트 tool 활동 표시.
- [x] tests: 툴 스키마·**테넌트 격리(LLM의 project_id 주입 무시)**·소유권 거부·미등록 툴·에이전트 툴 루프·멀티스텝 과금 — `test_chat_tools.py` 7 + `test_chat_graph.py`. 전체 chat 72 passed / 백엔드 2979 passed.
- [ ] 외부 MCP `mcp_registry.py`(관리자 화이트리스트·SSRF·graceful) — ⚠️ 상단 블로커(pydantic/uvicorn/httpx 핀 이동) 해결 후.

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
