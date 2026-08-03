## Why

도구와 MCP 호출이 영속 대화에서 중간 assistant/tool 메시지로 분리되어, 같은 모델 응답의 실행 과정과 최종 답변이 각각 다른 말풍선으로 렌더링된다. 사용자는 하나의 응답 안에서 도구 사용과 답변을 함께 읽어야 한다. 현재 채팅 시각도 브라우저 현지 시각 표현과 원본 UTC/현지 기록 계약이 분리되어 있지 않다.

## What Changes

- 같은 실행(run)에서 발생한 도구 호출·결과와 최종 assistant 답변을 하나의 assistant 말풍선으로 투영한다.
- 도구 카드의 완료 상태 옆에 실행 경과 시간을 작게 표시한다.
- 채팅 메시지는 UTC instant와 클라이언트 IANA timezone 기준 현지 wall-clock 시각을 함께 저장하고 API로 제공한다.
- 프런트엔드는 채팅 시각을 브라우저 현지 timezone으로 표시한다.

## Capabilities

### New Capabilities

- Inline chat tool activity rendering
- Dual UTC and local chat timestamp storage

### Modified Capabilities

- Durable chat message projection
- Chat message timestamp display

## Impact

- Backend chat message ORM, migration, completion/run persistence, and conversation response schema.
- Frontend chat tree projection, ChatWindow/ChatMessage rendering, submission contract, and component tests.
- 기존 기록은 UTC `created_at`을 유지하며 새 현지 컬럼이 없는 행도 정상적으로 표시한다.
