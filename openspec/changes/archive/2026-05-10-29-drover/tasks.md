## 25. 통합 모니터링 전(全) 리소스 가시성 + Drover 카운트 버그 수정 (2026-05-10)

### 25.1 동기

`/admin/monitoring` "클러스터 요약"이 일부 리소스만 집계하고 있었음:
- **Drover 클러스터 1대(`dms-cloud`, ACTIVE)인데 0으로 표시** — `_collect()`가 동기 함수인데 `k3s_db.list_all_clusters()`는 async라 `k3s_count: 0` 하드코딩(`admin.py:423-425` 옛 코드).
- DB 인스턴스 / Volume Snapshot/Backup / Share Snapshot / Image / Subnet / Security Group / Load Balancer / 사용자·프로젝트 수가 노출되지 않았음.

### 25.2 핵심 제약 — cross-project 보장

사용자 불만의 본질이 "admin scope 일부만 보이는 것"이라, 추가하는 모든 카운터는 **admin scope에서 cross-project 합산**을 보장.

- [x] Trove DB: `list_instances_admin_all_projects(conn)` (`/mgmt/instances`) — `count_instances`는 자기 프로젝트만이라 사용 안 함
- [x] Volume snapshot/backup: `conn.block_storage.snapshots/backups(all_projects=True)`
- [x] Share snapshot: `manila.list_share_snapshots(conn, all_tenants=True)` — `manila.py:710` 함수에 `all_tenants` 옵션 신규 추가
- [x] Octavia LB: `conn.load_balancer.load_balancers()` — admin scope에서 cross-project. `provisioning_status == "ACTIVE"`로 active 분리
- [x] Subnet/Security Group/Image: admin scope에서 SDK 기본 호출이 cross-project (admin.py 기존 패턴)
- [x] Identity: `_get_admin_ks_client().users.list()` / `.projects.list()` 길이

### 25.3 _collect async 변환 (Drover 버그 수정)

- [x] `get_monitoring_summary` 내부 `_collect`를 async로 변환. `cached_call`은 이미 `iscoroutinefunction` 분기로 async fn 처리(`cache.py:110-113`)
- [x] 동기 SDK 호출 15종을 `asyncio.to_thread + asyncio.gather`로 병렬 실행
- [x] k3s 클러스터는 `await k3s_cluster.list_all_clusters()` 직접 호출 — `k3s_count`/`k3s_active` 정상 노출

### 25.4 응답 스키마 확장 (호환 유지)

기존 4개 그룹 유지 + 누락 필드 추가 + 신규 그룹 2개:
- `storage`: `volume_snapshot_count`, `volume_backup_count`, `share_snapshot_count`, `image_count` 추가
- `network`: `subnet_count`, `security_group_count`, `load_balancer_count`, `load_balancer_active` 추가
- `containers`: `k3s_active` 추가 + `k3s_count` 정상 노출
- `data_services` (신규): `database_instance_count`
- `identity` (신규): `user_count`, `project_count`

### 25.5 드롭 항목 (의도적 제외)

- **Keypair 카운트** — Nova keypair는 per-user. admin도 자기 keypair만 보임 → cluster-wide 합산 불가능. 제외.
- **Swift container 카운트** — admin account 한정. cross-project 합산은 Swift reseller 권한 + 사용자 iteration 필요. 별도 PR.

### 25.6 프런트엔드 카드 재구성

- [x] `MonitoringSummary` interface에 신규 필드 (옵셔널 + `?? 0` 안전)
- [x] 스토리지 카드: 5줄 추가 (파일/볼륨 스냅샷·백업/파일 스냅샷/이미지)
- [x] 네트워크 카드: 3줄 추가 (Subnet / SG / LB)
- [x] 컨테이너 카드: Drover에 `(N active)` 배지
- [x] 신규 카드 2개: 데이터 서비스(Trove), Identity(사용자·프로젝트)

### 25.7 단위 테스트 — `test_admin_monitoring.py` 5건

- [x] k3s `[{status:"ACTIVE"}]` mock → `k3s_count == 1`, `k3s_active == 1` (Drover 버그 수정 회귀 방지)
- [x] k3s 빈 리스트 → 둘 다 0
- [x] 신규 그룹 `data_services` / `identity` 키 + 누락 필드 응답 포함 확인
- [x] 카운터 함수 일부 예외 시 다른 카운터 정상 (0 fallback)
- [x] async `_collect`가 `cached_call` `iscoroutinefunction` 분기에서 정상 동작

### 25.8 검증

- [x] 백엔드 단위 1307 → 1312 (+5), ruff/format 통과
- [x] 프런트엔드 빌드 통과
- 실 환경 검증 (사용자 1회): Drover 카드에 1 (1 active) 노출, 새 카드 2개 정상, 누락 리소스 표시

### 25.9 범위 외

- **각 리소스 상태 분포 차트 / 시계열** — 본 PR은 카운트만.
- **Keypair / Swift container** — admin scope 한계로 본 PR 제외 (위 25.5 참조).
- **인스턴스 status 외 세부 분포 (Trove/k3s/LB)** — total + active 1차만.
- **사이드바 재배치** — 기존 카드 유지.

---

