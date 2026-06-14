## 57. Identity 개요 허브 제거 및 통계 카드 이동

### 57.1 목표

사이드바 Identity 섹션의 "개요 허브"(`/admin/identity`) 를 제거하고, 4개 통계 카드(사용자·프로젝트·역할·그룹)를 관리자 개요(`/admin`)로 이동한다.

### 57.2 구현

- [x] `frontend/src/routes/admin/+page.svelte` — `IdentitySummary` 인터페이스/state 추가, `onMount`에서 `GET /api/admin/identity/summary` 호출, KpiCardRow와 ResourceDonutsCard 사이에 4개 StatTile 그리드 + `partial` 경고 배지 삽입
- [x] `frontend/src/lib/components/AdminSidebar.svelte` — Identity 섹션에서 "개요 허브" 항목 삭제
- [x] `frontend/src/routes/admin/identity/+page.svelte` (폴더째 삭제)

---

