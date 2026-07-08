# admin-volume-status-summary-filter

## Goal

관리자 전체 볼륨 페이지에서 전체 볼륨의 상태별 개수를 확인하고, 상태 카드를 눌러 기존 상태 필터를 적용할 수 있게 한다.

## Scope

- `backend/app/api/identity/admin.py`: 전체 프로젝트 Cinder 볼륨 상태 집계 API 추가 또는 기존 집계 노출.
- `backend/tests/`: 상태 집계 API 회귀 테스트.
- `frontend/src/routes/admin/volumes/+page.svelte`: 집계 로딩 및 기존 `statusFilter`와 연동.
- `frontend/src/lib/components/admin/volumes/**`: 상태 요약 카드 UI 추가/확장.
- `frontend/src/lib/types/volume.ts`: 필요한 타입 추가.

## Non-goals

- 기존 `AdminVolumeFilters.svelte` 상태 select를 중복 구현하지 않는다.
- 상태 개수를 현재 페이지의 `allVolumes`에서 계산하지 않는다. 페이지네이션/필터링과 독립된 aggregate source를 사용한다.
- 볼륨 테이블 액션/상세/쓰기 API 동작은 변경하지 않는다.
