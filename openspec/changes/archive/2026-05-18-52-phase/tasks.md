## Phase 51 — Phase 50 후속 프로덕션 버그 5건 수정

### Phase 51a — admin identity summary 500 fix

- [x] `_collect()` users/projects/roles 개별 try/except + partial 필드 반환
- [x] 외부 except에 `_logger.exception` 추가로 traceback 운영 가시화
- [x] pytest: 부분 실패 케이스 2종 추가 (test_admin_dashboard.py)

### Phase 51b — /dashboard/usage 무한 로딩 fix

- [x] 백엔드 응답 키 `volume_by_type` → `volumes_by_type` 통일
- [x] 프론트 `$effect` authReady 가드 추가 (activity 패턴 일관화)

### Phase 51c — ActivityLog 가시성 + db_status 노출

- [x] `services/activity.py` silent return → rate-limited warning (60s/1회)
- [x] `/api/dashboard/activity` 응답에 `db_status` 필드 추가
- [x] `hour_distribution` 응답 형식 단순 배열로 수정 (프론트 인터페이스 일치)
- [x] `dashboard/activity/+page.svelte` db_status=unavailable 안내 카드 표시
- [x] pytest: test_activity_silent_skip.py 신규 (3 cases)

### Phase 51d — 사용자용 notifications 분리 + 14d trend 안내 개선

- [x] 사용자 대시보드 `/api/admin/notifications` → `/api/dashboard/notifications` 교체
- [x] 백엔드 신규 endpoint: project-scoped ERROR 인스턴스 알림
- [x] 14d trend placeholder 문구 → "메트릭 수집 미설정 — 관리자에게 Grafana 설정 문의"
- [x] pytest: test_dashboard_notifications.py 신규 (3 cases)

### Phase 51e — /admin/monitoring Grafana 바로가기 섹션 제거

- [x] admin/monitoring/+page.svelte Grafana 섹션 삭제 (사이드바 9종과 완전 중복)
- [x] SectionHeader import 함께 제거

### Phase 51f — 검증

- [x] pytest 22 passed (test_admin_dashboard + test_dashboard_notifications + test_activity_silent_skip)
- [x] npm run check 59 errors baseline 유지

---

