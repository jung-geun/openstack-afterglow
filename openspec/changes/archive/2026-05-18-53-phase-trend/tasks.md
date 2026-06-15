## Phase 52 — Phase 51 후속 프로덕션 버그 5건 수정 + 14d trend 실데이터 연결

### Phase 52a — /dashboard/usage TypeError fix (응답 키 정렬)

- [x] top_instances: `flavor` → `flavor_name`, `status`/`disk_gb`/`usage_hours` 추가
- [x] `_list_flavors_as_dicts` vcpus/ram/disk 필드 추가
- [x] `_list_servers_as_dicts` name/created_at 필드 추가
- [x] volumes_by_type: `size_gb` → `total_gb`, `count` 필드 추가
- [x] isGpu(inst.flavor_name) TypeError 해소

### Phase 52b — /dashboard/usage-report TypeError fix (forecast 키 정렬)

- [x] 응답 `quota.forecast_pct` → `forecast.{vcpu_pct, memory_pct, storage_pct}`
- [x] memory_pct/storage_pct 신규 계산 추가
- [x] test_dashboard_usage_report.py 신규 4케이스

### Phase 52c — /admin/identity 허브 "undefined" fix

- [x] 응답에 flat alias 추가 (user_count/project_count/role_count/group_count/domain_count)
- [x] recent_users/recent_projects 최근 5건 반환
- [x] Phase 51a partial 케이스 호환 유지
- [x] test_admin_dashboard.py Phase 52c 케이스 추가

### Phase 52d — k3s 클러스터 상세 namespace 자동 로드

- [x] K3sClusterDetailPanel.svelte: ACTIVE 진입 시 loadNamespaces() 자동 호출
- [x] ConfigMap/Secret CRUD 네임스페이스별 동작 가능

### Phase 52e — 14d trend 카드 PromQL 실데이터 연결

- [x] /api/dashboard/metrics/trend endpoint 신규 (PromQL range_query, 14일치 1일 step)
- [x] Prometheus 미설치 시 prometheus_available=false + data=[] fallback (500 없음)
- [x] dashboard/+page.svelte Spark 컴포넌트 실데이터 연결
- [x] prometheus_available=false 시 observability 링크 포함 안내 표시
- [x] test_dashboard_metrics.py 신규 4케이스

### Phase 52f — 검증

- [x] pytest 41 passed (test_dashboard_new + test_dashboard_usage_report + test_dashboard_metrics + test_admin_dashboard + test_activity_silent_skip + test_dashboard_notifications)
- [x] npm run check 59 errors baseline 유지

