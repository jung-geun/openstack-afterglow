# instance-console-feedback

## Goal

인스턴스 상세 헤더의 콘솔 열기 버튼이 콘솔 URL 발급 대기 중 즉시 진행 상태를 표시한다.

## Scope

- Add local console-open loading/error state to the instance detail controller.
- Render loading/error feedback on the persistent instance detail header console button.
- Add focused frontend component coverage for default, loading, and error states.

## Non-goals

- Do not change the backend console URL endpoint or Nova/noVNC helper flow.
- Do not change the list-page console action feedback surface.
