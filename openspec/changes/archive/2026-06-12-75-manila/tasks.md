## 74. 빌드 고아화 수정 + Manila 직접 마운트 기능 (2026-06-12)

### 74.1 빌드 고아화(orphan) 수정

백엔드 재시작 시 인메모리 asyncio 태스크가 소멸되어 DB row가 영구적으로 "building" 상태에 머무르는 문제.
`cleanup_stale_builds()`가 구현됐으나 startup에 연결되지 않아 잔류 VM/port/share가 정리되지 않음.

- [x] `reconcile_orphan_builds()` 구현 — 비터미널 row 검사 후 VM SHUTOFF+sentinel 성공이면 prebuilt 승격, 그 외 error 처리 + OpenStack 리소스 정리
- [x] `main.py` startup에 reconcile 연결
- [x] asyncio task GC 방지 — 모듈 레벨 set에 태스크 참조 보관
- [x] prebuilt 가시성 버그 수정 — `api/common/libraries.py` service conn + `include_public=True` 로 통일
- [x] 빌드 모달 콘솔 로그 개선 — SHUTOFF VM은 `console_log_excerpt` fallback 표시
- [x] pytest — reconcile 시나리오(SHUTOFF+sentinel→complete, VM 없음→error) + prebuilt 가시성

### 74.2 VM 생성 시 기존 파일 스토리지 데이터 마운트

라이브러리 OverlayFS와 독립적으로 기존 Manila share를 사용자 지정 경로에 마운트.

- [x] `DataMountSpec` Pydantic 모델 — mount_point 화이트리스트 validator (절대경로, `/opt/layers` 하위 금지)
- [x] `CreateInstanceRequest.data_mounts` 필드 추가
- [x] `_prepare_data_mounts()` — share 소유권 검증, NFS(CIDR rule)/CephFS(cephx rule) access rule 생성
- [x] `generate_userdata()` — `data_mounts` 파라미터 추가, `data_mounts.sh.j2` 템플릿 (사용자 경로 마운트 + fstab 등록)
- [x] VM 마법사 UI — `WizardStep5Config.svelte`에 파일 스토리지 마운트 섹션
- [x] pytest — 마운트 스펙 생성/롤백/경로 검증/IDOR/인젝션 방어

### 74.3 실행 중 VM에 파일 스토리지 연결

- [x] `POST/GET/DELETE /api/instances/{server_id}/storage-attachments` — access rule 생성/조회/삭제, mount_command 반환
- [x] 인스턴스 상세 페이지 — 파일 스토리지 섹션(연결/해제 버튼, 마운트 명령 복사)
- [x] pytest — attach/detach/IDOR/삭제 시 rule 정리

### 74.4 share network UI 안내

- [x] `file-storage/networks/+page.svelte` — DHSS=False 환경 안내 (share network 불필요 명시)
- [x] 파일 스토리지 생성 마법사 — share network 선택 선택 사항 안내

---

