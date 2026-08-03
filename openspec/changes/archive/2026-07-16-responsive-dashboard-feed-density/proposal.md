# Goal

대시보드가 화면 높이에 맞춰 최근 인스턴스와 시스템 알림을 더 많이 보여 주되, 낮은 화면에서는 핵심 행을 우선 유지한다.

# Scope

- overview summary의 최근 인스턴스 상한을 안전한 범위에서 요청할 수 있게 한다.
- 대시보드는 12개 행을 받아 viewport-height CSS로 5·8·10·12개를 보여 준다.
- 시스템 알림 목록은 viewport-height에 비례한 내부 스크롤 영역을 사용한다.
- backend와 frontend 회귀 테스트를 추가한다.

# Out of scope

- 전체 인스턴스/알림 페이지의 pagination 또는 데이터 모델 변경
- dashboard API의 legacy 경로 추가
