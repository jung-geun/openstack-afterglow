## Why

NFS 마운트 옵션과 라이브러리(레이어) 카탈로그가 백엔드에는 있으나 프론트 UI가 미비하다. 사용자가 GUI에서 NFS 옵션을 지정하고 사전 빌드 라이브러리를 탐색·선택할 수 있어야 한다.

## What Changes

- VM 생성 위저드에 NFS 마운트 옵션 UI (export/옵션 입력 + 검증)
- 라이브러리 카탈로그 탐색 화면 (사전 빌드 레이어 가용성·메타 표시)

## Impact

`frontend/src/lib/components/`(VM 생성 위저드, 라이브러리 카탈로그), 기존 `/api/libraries`·파일 스토리지 API 재사용. 백엔드 변경 최소.
