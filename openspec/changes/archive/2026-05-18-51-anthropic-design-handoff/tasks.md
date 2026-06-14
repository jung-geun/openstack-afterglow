## Phase 50 — Anthropic Design Handoff 적용 (대시보드 4 + 관리자 4 페이지)

### Phase 50a — 디자인 토큰 + UI primitive 5종 신규

- [x] --admin-tone CSS 변수 추가 (layout.css dark/light)
- [x] Pill.svelte 신규 (8 tone)
- [x] SectionHeader.svelte 신규 (uppercase + meta + right slot)
- [x] Spark.svelte 신규 (SVG path, fixedWidth/stretch)
- [x] Donut.svelte 신규 (SVG strokeDasharray + center slot)
- [x] CapacityBar.svelte 신규 (80%/95% 자동 톤)
- [x] StatTile.svelte admin-tone accent 추가
- [x] lib/components/ui/index.ts barrel export 신규
- [x] npm run check baseline 유지 (59 errors ≤ 62 baseline)

### Phase 50b — 백엔드 endpoint (대시보드 4-A~4-E) + pytest

- [x] backend/app/api/dashboard/ 5개 endpoint
- [x] backend/app/models/dashboard.py Pydantic 모델
- [x] backend/tests/test_dashboard_*.py pytest
- [x] pytest 통과

### Phase 50c — 백엔드 endpoint (관리자 A-1~A-7) + pytest

- [x] admin_dashboard.py A-1~A-6 endpoint
- [x] admin_identity.py A-7 summary
- [x] bulk-action ActivityLog 자동 기록
- [x] backend/tests/test_admin_dashboard.py require_admin 거부 케이스 포함
- [x] pytest 통과

### Phase 50d — 사이드바 nav + 신규 라우트 3종 스켈레톤

- [x] Sidebar.svelte 대시보드 섹션 4개 메뉴
- [x] dashboard/usage, usage-report, activity 라우트 스켈레톤

### Phase 50e — 대시보드 4 페이지 마크업 이식

- [x] routes/dashboard/+page.svelte PageOverview 이식 (14d 추세 + 알림 섹션 추가)
- [x] routes/dashboard/usage/+page.svelte PageUsage 이식
- [x] routes/dashboard/usage-report/+page.svelte PageUsageReport 이식
- [x] routes/dashboard/activity/+page.svelte PageActivity 이식
- [x] 비용/요금 단어 0건

### Phase 50f — 관리자 4 페이지 마크업 이식

- [x] routes/admin/+page.svelte 알림 배너 + AutoRefresh 추가
- [x] routes/admin/identity/+page.svelte 허브 신설 (3탭 + admin-tone)
- [x] routes/admin/monitoring/+page.svelte Grafana 바로가기 9종 추가
- [x] routes/admin/instances/+page.svelte 5 KPI tiles 추가
- [x] AdminSidebar.svelte Identity 허브 링크 추가
- [x] bulk action ActivityLog 백엔드 검증 완료 (Phase 50c pytest)

### Phase 50g — 8 페이지 AutoRefresh 통합

- [x] 8 페이지 createAutoRefresh 적용 완료 (Phase 50e/50f에서 통합)
- [x] localStorage 키 분리 (dashboard-home/usage/usage-report/activity, admin-overview/identity/monitoring/instances)

### Phase 50h — milestone 정리 + 디자인 회귀 점검

- [x] 비용/요금 단어 0건 (dashboard/admin 전체)
- [x] 하드코딩 hex 0건 (4개 신규 대시보드 + 4개 관리자 페이지)
- [x] 신규 4 대시보드 페이지 OpenStack 서비스명 0건
- [x] npm run check baseline 59 errors 유지
- [x] milestone.md 50a~50h [x]

---

