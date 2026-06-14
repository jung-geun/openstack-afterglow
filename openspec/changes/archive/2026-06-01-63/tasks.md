## 62. 목록 표 페이지네이션 위치 표시 (2026-06-01)

### 62.1 목표

관리자·대시보드의 모든 목록 표에 현재 페이지 번호를 표시해 탐색 위치를 한눈에 파악할 수 있게 한다.

### 62.2 구현

- [x] `frontend/src/lib/components/ui/Pagination.svelte` (신규) — 공용 페이지네이션 컴포넌트 (이전·다음 버튼 + 중앙 페이지 표시). `totalPages` 제공 시 "N / M", 없으면 "페이지 N". `total`·`pageSize` 제공 시 범위("X개 중 A–B개") 추가 표시. `note` prop으로 부가 텍스트 지원.
- [x] `frontend/src/lib/components/ui/index.ts` — `Pagination` export 추가
- [x] `frontend/src/lib/components/admin/images/AdminImagesTable.svelte` — `<Pagination>` 적용 (커서, "페이지 N")
- [x] `frontend/src/lib/components/admin/instances/AdminInstanceTable.svelte` — `<Pagination>` 적용 (커서, "페이지 N")
- [x] `frontend/src/lib/components/admin/ports/PortsTable.svelte` — `<Pagination>` 적용 (커서, "N개 포트 · 페이지 N")
- [x] `frontend/src/lib/components/admin/users/AdminUsersTable.svelte` — `<Pagination>` 적용 (커서, "페이지 N"), `page` prop 추가
- [x] `frontend/src/routes/admin/users/+page.svelte` — `page={markerStack.length + 1}` 전달
- [x] `frontend/src/routes/admin/projects/+page.svelte` — 인라인 버튼 블록 → `<Pagination>` 교체 (커서, "페이지 N")
- [x] `frontend/src/routes/admin/volumes/+page.svelte` — `AdminVolumePagination` → `<Pagination>` 교체 (커서, "페이지 N")
- [x] `frontend/src/lib/components/library/LayerCatalogTable.svelte` — `<Pagination>` 적용 (offset, "페이지 N")
- [x] `frontend/src/routes/admin/file-storage/+page.svelte` — `AdminFileStoragePagination` → `<Pagination>` 교체 (클라이언트 슬라이싱, "N / M")
- [x] `frontend/src/lib/components/admin/flavors/AdminFlavorsTable.svelte` — `<Pagination>` 적용 (클라이언트 슬라이싱, "N개 중 A–B개 · N / M", 필터 note 보존)
- [x] `frontend/src/lib/components/admin/volumes/AdminVolumePagination.svelte` — 삭제 (공용 컴포넌트로 통합)
- [x] `frontend/src/lib/components/admin/file-storage/AdminFileStoragePagination.svelte` — 삭제 (공용 컴포넌트로 통합)
- [x] `frontend/src/lib/components/admin/file-storage/AdminFileStoragePagination.svelte` — 삭제 (공용 컴포넌트로 통합)

---

