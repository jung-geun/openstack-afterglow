# VM 생성 위저드 반응형 네비게이션 정리

## Why

모바일의 compact progress strip은 헤더의 현재 단계 정보와 중복되어 세로 공간을 차지한다. 모바일 네비게이션은 콘텐츠 끝으로 밀려 화면 하단에서 바로 조작할 수 없고, 데스크톱 stepper도 현재 정보 밀도에 비해 높다.

## What Changes

- 모바일에서는 중복된 stepper/progress strip을 숨기고 헤더의 단계 정보만 유지한다.
- 데스크톱 full stepper의 padding과 step dot 크기를 줄여 높이를 낮춘다.
- 모든 viewport에서 wizard footer를 SlidePanel 스크롤 컨테이너 하단에 sticky로 유지한다.
- 모바일 safe-area inset을 footer padding에 반영한다.
- 반응형 stepper와 footer 위치 회귀 테스트를 갱신한다.

## Out of Scope

- 위저드 단계 순서, 입력 데이터, 배포 동작 변경
- SlidePanel의 전역 스크롤 동작 변경
