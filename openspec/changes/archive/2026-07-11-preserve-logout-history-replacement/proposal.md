# Why

세션 폐기 컴포넌트가 `clearAuth()`를 호출하면 전역 인증 guard 또는 401 handler가 먼저 `/login` push navigation을 실행할 수 있어, 뒤따르는 replace navigation이 history entry를 보장하지 못한다. mock 모드는 stale profile 재진입 없이 명시적 로그아웃과 같은 로그인 경로로 종료되어야 한다.

# What Changes

- 전역 비인증 guard와 401 handler의 로그인 이동도 `replaceState: true`로 실행한다.
- 세션 폐기는 새 refresh를 동기 차단하는 revocation fence를 세우고, 동일 탭에서 이미 실행 중인 refresh와 localStorage로 관찰된 cross-tab winner가 갱신한 최신 access token을 먼저 폐기한다. 401 handler는 해당 폐기 중인 흐름의 로컬 정리·이동을 가로채지 않는다. 서버 또는 원격 탭과의 refresh/logout 직렬화는 이 변경의 범위가 아니다. mock 모드는 `mockup=off` 로그인 경로로 종료한다.
- 실제 세션 보안 컴포넌트·401 redirect·동시 refresh/401·cross-tab winner·만료 토큰 logout 재시도·mock profile 종료 회귀 테스트로 모든 명시적 로그아웃이 로그인 페이지에 머무는 계약을 고정한다.
