## Implementation Tasks

### Phase 1 — 설정 동기화 + 백엔드 사용량 미러링 API

- [x] `backend/app/config.py` — `_load_toml()` flat dict + `Settings`에 `librechat_mongo_url`(비밀), `librechat_base_url` 필드 추가
- [x] `afterglow.conf.example` — `[chat]` 섹션(mongo_url, base_url) 예시/주석 추가
- [x] `generate_k8s.py` — `librechat_mongo_url`은 `render_secret()`, `librechat_base_url`은 `_render_toml_for_k8s()`/`render_configmap()`(`APP_LIBRECHAT_BASE`)에 반영
- [x] MongoDB 읽기 클라이언트 추가(`motor` 의존성 `pyproject.toml`, `backend/app/services/librechat_mongo.py` — 연결 lazy init + 읽기 전용 헬퍼)
- [x] `backend/app/api/chat/usage.py` — `GET /usage`(prefix `/api/v1/chat`), `get_token_info` 의존, username으로 `users`→`transactions` 조회·집계, 실패 시 found=false로 200(fail-open, Grafana 패턴과 동일)
- [x] `backend/app/main.py` — `include_router(chat_usage_router, prefix="/api/v1/chat", ...)` 등록
      (`_AUDIT_PREFIX_MAP`은 GET-only·app-DB 리소스 아님이라 등록 대상 아님 — 상세는 아래 "구현 중 확정된 결정" 참고)
- [x] `backend/tests/test_chat_usage.py` — 인증 필수(401), found/not-found 응답, username 격리(타 사용자 데이터 노출 없음) 확인
- [x] `backend/tests/test_librechat_mongo.py` — fake Motor 컬렉션으로 실제 쿼리 로직 end-to-end 검증. **보안 수정**: username을 `$regex`에 그대로 보간하면 정규식 메타문자(예: `.`)로 다른 사용자와 매칭될 수 있어 `re.escape()` 적용(`librechat_mongo.py`), 회귀 테스트로 고정(`a.b` 사용자가 `axb` 사용자와 매칭되지 않음을 확인)

### Phase 2 — 프론트엔드 iframe 임베드 + 네비게이션

- [x] `frontend/src/lib/types/siteConfig.ts` / `frontend/src/lib/config/site.ts` / `frontend/src/lib/server/config.ts` — `runtime.librechat_base` 추가(`[chat] base_url` TOML 로드)
- [x] `frontend/src/hooks.server.ts` — CSP `frame-src`에 `librechat_base` 추가(iframe 임베드 허용)
- [x] `frontend/src/lib/components/LibreChatEmbed.svelte` — `Card` 프리미티브 + 디자인 토큰으로 iframe(sandbox 속성) 조립 + 새 탭 폴백 링크
- [x] `frontend/src/routes/dashboard/chat/+page.svelte` — `LibreChatEmbed` 사용
- [x] `frontend/src/lib/components/Sidebar.svelte` — `sections` 배열에 "AI 채팅" 메뉴 추가
- [x] `frontend/src/lib/config/nav.ts` — `userNavSections`에 동일 항목 추가
- [x] `frontend/src/lib/config/routes.ts` — `ROUTE_LABELS`에 `chat: 'AI 채팅'` 등록
- [x] **설정 기반 활성화 게이팅(2026-07-13, 사용자 요청)**: `[chat] base_url` 미설정 시 "AI 채팅" 메뉴가 노출되지 않도록 게이팅. `Sidebar.svelte`(섹션/아이템 `service: 'chat'` + `runtime.librechat_base` 검사), `nav.ts`(동일 메타데이터), `CmdPalette.svelte`(팔레트 항목 필터). 직접 URL 진입 시에는 `LibreChatEmbed`의 기존 "구성되지 않음" 폴백이 표시됨. 회귀 테스트: `src/routes/__tests__/chat-gated-surfaces.test.ts`

### Phase 3 — 사용량 리포트 통합 + 검증

- [x] `frontend/src/routes/dashboard/usage-report/+page.svelte` — LLM 토큰 사용량 섹션 추가(`/api/v1/chat/usage` 호출, `Card` 프리미티브로 디자인 토큰 부채 회피)
- [x] **실배포 버그 수정(2026-07-13)**: 실제 배포 후 iframe 안에서 LibreChat이 GitLab OIDC로 자동 리다이렉트(`OPENID_AUTO_REDIRECT`) 시 CSP 위반으로 차단됨. Root cause: `frame-src`는 iframe 최초 로드뿐 아니라 그 프레임의 이후 자체 내비게이션(리다이렉트)까지 통제하므로, LibreChat이 내장된 프레임을 GitLab으로 리다이렉트하려면 Afterglow의 `frame-src`에도 GitLab origin이 있어야 함(LibreChat 자신의 응답에는 CSP 헤더가 아예 없음을 실제 응답 헤더로 확인해 반증). `frontend/src/lib/server/config.ts`(`[gitlab_oidc] enabled`+`gitlab_url` → `runtime.gitlab_base`, GitLab OIDC 활성화 시에만), `frontend/src/hooks.server.ts`(`buildFrameSrc`에 `gitlab_base` 추가)로 수정. 회귀 테스트: `frontend/src/lib/server/config.test.ts`("includes librechat_base and gitlab_base in frame-src")
- [ ] 대시보드 로그인 상태에서 `/dashboard/chat` 진입 시 재로그인 없이 뜨는지 수동 확인(devtools에서 iframe 쿠키 same-site 전송 확인) — 실제 `chat.dmslab.re.kr`/`cloud.dmslab.re.kr` 배포 환경 필요, 로컬에서 검증 불가
- [ ] iframe CSP `frame-ancestors` 통과 확인 + 새 탭 폴백 동작 확인 — 상동
- [ ] `/api/v1/chat/usage` 응답이 실제 LibreChat 사용량과 일치하는지, 타 사용자 데이터 미노출 수동 확인 — 상동(실제 LibreChat MongoDB 접근 필요)
- [x] `npm run test:backend` 통과 확인 (2880 passed, 42 skipped) + `npm run lint:backend` 통과 확인
- [ ] `npm run test:frontend` — 내 변경분(LibreChatEmbed.svelte, usage-report 등)은 통과. **단, 저장소에 이미 존재하던 미커밋 WIP(`dashboard/network/vpn/+page.svelte`, loadbalancers/database/object-storage 등)로 인한 기존 실패가 남아있어 리포지토리 전체 기준으로는 test:all이 아직 green이 아님** — 이 항목들은 이번 LibreChat 작업 범위 밖이므로 별도 확인 필요

### 구현 중 확정된 결정 (계획 대비 변경)

- **신원 조인**: GitLab sub/email이 아니라 **Keystone `username`**으로 조인한다. `get_token_info()`가 반환하는 필드에는 GitLab sub/email이 없고 `username`만 존재하기 때문(GitLab federation 매핑 결과). LibreChat 쪽 `users.username`과 대소문자 무시로 매칭.
- **`_AUDIT_PREFIX_MAP` 미등록**: 이 맵은 mutation(POST/PUT/PATCH/DELETE) 성공 시 자동 활동 로그를 남기는 감사 미들웨어용이며 GET 전용 엔드포인트에는 적용되지 않는다. `/api/v1/chat`은 앱 DB 소유권 리소스가 아니라 외부 LibreChat 리소스의 읽기 전용 조회이므로 등록 대상이 아니다.

### 인스턴스 운영 설정 (코드 변경 아님, 별도 확인 필요)

- [ ] 기존 LibreChat(`chat.dmslab.re.kr`) nginx/ingress에서 `X-Frame-Options` 제거 + `Content-Security-Policy: frame-ancestors https://cloud.dmslab.re.kr` 설정
- [ ] 기존 LibreChat `.env`에 `OPENID_AUTO_REDIRECT=true` 반영
- [ ] Afterglow 백엔드 → LibreChat MongoDB 읽기 전용 네트워크 경로/전용 읽기 계정 확보, `afterglow.conf`의 `[chat] mongo_url`/`base_url` 실값 설정
- [ ] **LibreChat의 GitLab OIDC는 Afterglow가 쓰는 것과 동일한 GitLab OAuth Application(같은 client_id/client_secret)을 재사용**한다.
      GitLab Application 설정에서 Redirect URI 목록에 `https://chat.dmslab.re.kr/oauth/openid/callback`을 추가로 등록하고,
      `OPENID_CLIENT_ID`/`OPENID_CLIENT_SECRET`은 Afterglow(`gitlab_oidc_client_id`/`_client_secret`)와 동일한 값을 사용한다.
      같은 Application을 쓰면 사용자가 Afterglow 로그인 시 이미 승인한 동의(Authorize) 화면이 LibreChat에서 재요청되지 않는다.
      단, **동의 화면 스킵과 "재로그인 스킵"은 별개**다 — 재로그인 스킵은 GitLab 자체 세션 쿠키 존재 여부에 달려있다.
- [ ] **[별도 조사 필요, 이 저장소 밖 이슈] Grafana의 GitLab OIDC 연동에서 매번 GitLab 로그인 화면이 재요청되는 문제.**
      Afterglow는 GitLab 버튼으로 로그인해 GitLab 세션 쿠키가 생성됨을 확인했는데도 재로그인이 요구됨 → 단순 미승인 상태가 아니라
      GitLab 세션이 실제로 인식되지 않고 있다는 뜻. 확인 대상(Afterglow 코드베이스가 생성/관리하지 않는 영역 — Grafana `grafana.ini`/
      환경변수, GitLab Application 설정): (1) Grafana의 OAuth authorize 요청에 `prompt=login` 등 강제 재인증 파라미터가 섞여 있는지,
      (2) Grafana가 실제로 `git.dmslab.re.kr`(Afterglow와 동일 인스턴스)로 리다이렉트하는지 아니면 다른 GitLab 주소로 잘못 설정됐는지,
      (3) GitLab 세션 쿠키의 Max-Age/도메인 스코프가 예상대로인지. LibreChat 연동 시에도 같은 증상이 재발할 수 있으니 위 (1)(2)를
      LibreChat `.env` 설정 시에도 함께 점검한다.

### 실배포 검증에서 발견된 두 번째 이슈 — GitLab X-Frame-Options (아키텍처 한계, 코드로 해결 불가)

client_id 공유(동일 GitLab OAuth Application, Redirect URI에 `chat.dmslab.re.kr/oauth/openid/callback` 등록 완료 확인됨)를
적용하고 CSP `frame-src`도 고쳤는데도, 실배포 테스트에서 새 증상 발견:

```
Refused to display 'https://git.dmslab.re.kr/' in a frame because it set 'X-Frame-Options' to 'sameorigin'.
```

**Root cause**: GitLab은 로그인 폼 또는 최초 동의(Authorize) 화면처럼 **실제 HTML 페이지를 렌더링해야 하는 순간**에는
`X-Frame-Options: sameorigin`으로 프레임 내 표시를 거부한다(피싱/클릭재킹 방지 표준 동작). 반대로 GitLab이 기존 세션+기존
동의를 인식해 **순수 302 리다이렉트**만으로 처리를 끝낼 수 있으면 이 헤더는 문제가 되지 않는다(리다이렉트 자체는 iframe
안에서도 정상 통과 — 실측 확인됨). 테스트 시점에 사용자가 GitLab에 방금 로그인한 상태였는데도 화면이 떴다는 건, 이번이
이 client_id+scope 조합에 대한 **최초 동의(1회성)** 였을 가능성이 높음.

**해결 불가 vs 1회성 비용**:
- GitLab의 X-Frame-Options을 끄는 건 권장하지 않는다(클릭재킹 방어를 무력화함). 코드/설정으로 우회할 방법 없음.
- 다만 사용자당 **딱 한 번만** 겪는 문제다: 이 Application+scope에 대해 한 번 로그인/동의를 완료하면 GitLab은 이후 세션이
  유효한 동안 리다이렉트만으로 처리한다. 게다가 LibreChat 자신도 로그인 성공 시 `refreshToken` 쿠키(SameSite=strict, 약
  7일 만료)를 `chat.dmslab.re.kr`에 심는데, `cloud.dmslab.re.kr`과 같은 상위 도메인(`dmslab.re.kr`)이라 이 쿠키가 iframe
  안에서도 정상 전송된다. 즉 최초 1회를 새 탭에서 완료하면 이후 최대 7일은 iframe에서 바로 인증된 화면이 뜬다.

**적용한 완화책(코드)**: `frontend/src/lib/components/LibreChatEmbed.svelte` — localStorage 플래그(`librechat_onboarded`)로
최초 방문 여부를 추적해, 처음 방문 시 "최초 1회는 로그인을 위해 새 탭에서 열어야 합니다" 안내 배너 + "새 탭에서
로그인하기" 버튼을 iframe 위에 표시한다. 클릭 시 플래그를 저장해 다음부터는 배너 없이 iframe만 보여준다.
X-Frame-Options 차단 자체는 크로스오리진이라 JS로 감지할 수 없으므로(항상 배너를 보여주는 대신) localStorage
휴리스틱으로 "최초 방문 여부"만 추정하는 방식을 택함 — 사용자가 다른 기기/브라우저로 처음 접속하면 다시 뜸(의도된 동작).

- [ ] 실배포에서 "새 탭에서 로그인하기" 완료 후 같은 브라우저로 `/dashboard/chat` 재방문 시 GitLab을 거치지 않고 바로
      인증된 채팅 화면이 뜨는지 확인(로컬 검증 불가, 실 배포 환경 필요)
