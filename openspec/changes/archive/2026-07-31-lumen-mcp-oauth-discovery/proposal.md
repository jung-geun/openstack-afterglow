# Lumen MCP OAuth and Discovery

## Goal
MCP OAuth 완료 후 Lumen의 MCP 설정 화면으로 복귀시키고, 자연어 MCP 목록 요청이 등록·인증된 도구를 실제로 로드하게 한다.

## Scope
- OAuth callback의 안전한 frontend origin 검증은 유지하면서 Lumen chat route에 MCP settings 복귀 상태를 전달한다.
- Lumen route가 callback 상태일 때 설정 overlay의 MCP 서버 section을 연다.
- On-demand catalog가 MCP라는 핵심어를 포함한 자연어 질의에서 활성 MCP bindings를 선택한다.
- 명시적 속성을 가진 nested MCP object schema를 closed schema로 정규화하되, 동적 map schema는 계속 거부한다.

## Non-goals
- OAuth callback origin allowlist, PKCE/state/nonce 검증을 변경하지 않는다.
- 동적 key/value map을 허용하도록 tool schema 안전 정책을 완화하지 않는다.
- MCP 서버 등록 UI나 기존 OAuth credential storage를 변경하지 않는다.

## Verification
- OAuth callback redirect unit test와 Lumen settings-route test를 추가한다.
- Korean natural-language MCP discovery query가 valid MCP schemas를 로드하는 tool-runtime test를 추가한다.
- nested schema closure 및 dynamic map rejection을 테스트한다.
