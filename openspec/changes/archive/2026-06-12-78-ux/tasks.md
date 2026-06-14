## 77. 하이퍼바이저 페이지 UX 개선 4종

### A. VM 상세 이동
- [x] `HypervisorDetailPanel.svelte` — VM 목록 이름 버튼화 + `onOpenDetail(id, pid)` prop
- [x] `routes/admin/hypervisors/+page.svelte` — `SlidePanel` + `InstanceDetailPanel` 추가 (admin/instances 패턴 재사용)

### B. CPU 모델 표시
- [x] `backend/app/services/nova.py` — `extract_cpu_model(h)` 모듈 레벨 함수 승격 (dict/JSON string 양방향)
- [x] `backend/app/api/identity/admin.py` — `list_hypervisors` + `get_hypervisor_detail` 응답에 `cpu_model` 추가
- [x] `HypervisorRow` 인터페이스 + `HypervisorTable.svelte` — CPU 모델 정렬 가능 칼럼 추가 (lg 이상만 표시)
- [x] `HypervisorDetail` 인터페이스 + `HypervisorDetailPanel.svelte` — 기본 정보 섹션에 CPU 모델 행 추가

### C. 콜드 마이그레이션 개선
- [x] `nova.py` — `list_compute_hosts(cpu_filter=True)` 파라미터 추가 (False이면 소스 제외만, CPU 모델 무관)
- [x] `nova.py` — `cold_migrate_server(host=None)` — host 지정 시 microversion 2.56으로 대상 호스트 직접 지정
- [x] `admin.py` — `/compute-hosts?cpu_filter=false` + `/cold-migrate` body `{host}` 지원
- [x] `instanceDetailController.svelte.ts` — `loadMigrateHosts(type)` cold이면 `cpu_filter=false`, `doMigrate` cold에 host 전달
- [x] `InstanceDetailPanel.svelte` — `openMigrateModal`에서 type 전달
- [x] `MigrateModal.svelte` — cold 시 "모든 호스트 표시 (CPU 모델 무관)" 힌트
- [x] `HypervisorMigrateModal.svelte` — server_id 전달 + cold이면 cpu_filter=false + cold host body 전송 + CPU 힌트

### D. Node Exporter 영역 제거
- [x] `routes/admin/hypervisors/+page.svelte` — GrafanaEmbed 블록 + import 제거 (모니터링 > 노드 메뉴 중복)

### 테스트
- [x] `tests/test_admin_migration.py` — `extract_cpu_model` 6종 + `cpu_filter=False` 2종 + `cold_migrate_server(host)` 2종 + 엔드포인트 cold host/cpu_filter 3종 (39 passed)


---

