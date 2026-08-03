## Why

연구실은 이미 LibreChat(`chat.dmslab.re.kr`)을 운영 중이며 MongoDB에 사용자별 토큰 사용량(Transactions 컬렉션)과 채팅 기록이 이미 축적되어 있다. Afterglow 클라우드 플랫폼(`cloud.dmslab.re.kr`) 사용자에게 이 검증된 LLM 채팅 시스템을 내장 서비스로 제공하고, 토큰 사용량을 Afterglow 대시보드에서도 확인할 수 있게 한다. 토큰 회계·채팅 기록·모델 라우팅을 갖춘 시스템을 새로 만드는 대신, 기존 LibreChat 인스턴스를 그대로 iframe 임베드하고 사용량 데이터만 읽기 전용으로 미러링하는 하이브리드 방식을 채택한다.

## What Changes

- Afterglow 대시보드에 `/dashboard/chat` 페이지를 추가해 기존 `chat.dmslab.re.kr` LibreChat 인스턴스를 iframe으로 임베드한다. Afterglow와 LibreChat이 이미 공유하는 GitLab OIDC 세션 덕분에 재로그인 없이 SSO가 성립한다(`OPENID_AUTO_REDIRECT=true`). 공통 상위도메인(`dmslab.re.kr`)이라 iframe 세션 쿠키가 same-site로 흐른다.
- 기존 LibreChat 인스턴스 앞단에 iframe 허용 헤더(`X-Frame-Options` 제거, `Content-Security-Policy: frame-ancestors`)를 설정한다(운영 설정, 신규 배포 아님).
- Afterglow 백엔드가 LibreChat MongoDB의 `transactions` 컬렉션을 읽기 전용으로 조회해 현재 로그인 사용자의 토큰 사용량을 집계하고, `/dashboard/usage-report`에 노출한다. 신원 조인은 GitLab `sub` 우선, email 폴백.
- 신규 MongoDB/LibreChat 배포, 신규 LiteLLM 구성은 이번 범위에 포함하지 않는다(기존 인스턴스 재사용, LiteLLM은 별도로 구성 중).

## Capabilities

### New Capabilities

- **chat-embed**: 대시보드 `/dashboard/chat` 페이지에서 기존 LibreChat 인스턴스를 iframe으로 임베드하고 SSO로 재로그인 없이 진입.
- **chat-usage-mirror**: LibreChat MongoDB `transactions` 컬렉션을 읽기 전용 조회해 로그인 사용자 본인의 토큰 사용량을 집계·노출(`/api/v1/chat/usage`).

### Modified Capabilities

- **usage-report**: 기존 OpenStack 리소스 사용량 화면에 LLM 토큰 사용량 섹션 추가.

## Impact

- **백엔드**: `app/api/chat/usage.py` 신규 라우터(`/api/v1/chat`, `get_token_info` 의존, 읽기 전용). `app/main.py`에 `include_router` + `_AUDIT_PREFIX_MAP`에 `("/api/v1/chat", "chat")` 등록. `app/config.py`에 `librechat_mongo_url`(비밀)·`librechat_base`(일반) 필드 추가. `generate_k8s.py`/`afterglow.conf.example` 동기화. MongoDB 읽기 클라이언트(`motor`) 신규 의존성.
- **프론트엔드**: `frontend/src/routes/dashboard/chat/+page.svelte` 신규, `frontend/src/lib/components/LibreChatEmbed.svelte` 신규(`GrafanaEmbed.svelte` 패턴 참고). `Sidebar.svelte`/`nav.ts`/`routes.ts`에 메뉴 3곳 등록. `site.ts`에 `librechat_base` 런타임 설정. `dashboard/usage-report/+page.svelte`에 사용량 섹션 추가.
- **테스트**: `backend/tests/test_chat_usage.py` 신규(인증 필수, 타 사용자 데이터 격리, 집계 정확도, Mongo 스키마 가정 고정).
- **인스턴스 운영(코드 외)**: 기존 LibreChat nginx/ingress에 iframe 허용 헤더 설정, `OPENID_AUTO_REDIRECT=true` 반영.
- **기존 기능에 대한 영향**: `usage-report` 페이지에 섹션 추가 외 기존 엔드포인트/모델 변경 없음.
