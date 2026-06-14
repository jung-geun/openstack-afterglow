## 5. 클라우드 운영 추가 기능

> **목표**: 프로덕션 환경 운영에 필요한 기능 추가

- [x] 5.1 OverlayFS 상태 모니터링 에이전트
  - [x] VM 내부 헬스체크 스크립트 (`/opt/union/scripts/health-check.sh`)
  - [x] 마운트 상태: `mountpoint -q /opt/layers/merged` 확인
  - [x] NFS/CephFS 연결 상태: `timeout 5 stat` (hard mount hang 방지)
  - [x] 디스크 사용량: upper 볼륨 사용률 경고 (90%/95% 임계)
  - [x] 결과를 backend API (`POST /api/instances/{id}/health/report`)로 리포트 (Bearer 토큰 인증, 30분 TTL Redis 캐시)

- [x] 5.2 Manila Share Snapshot 관리
  - [x] 사전 빌드 라이브러리의 스냅샷 생성/복원 기능 (`POST /api/share-snapshots`, `POST /api/share-snapshots/{id}/revert`)
  - [x] 버전 업데이트 시 스냅샷으로 롤백 가능 (`revert_to_snapshot` — Manila action API)
  - [x] `backend/app/services/manila.py` — 스냅샷 API 연동 (create/list/get/delete/revert 5개 함수)

- [x] 5.3 볼륨 백업 및 복구
  - [x] Cinder upper 볼륨의 정기 백업 스케줄링 — `auto_backup.py` + `_auto_backup_loop`
  - [x] 백업에서 복구 시 OverlayFS 재구성 자동화 — `existing_upper_volume_id` + workdir 정리
  - [x] 볼륨 목록 ActionMenu 수동 백업 생성 — `VolumeBackupModal.svelte` + `POST /api/volumes/backups` (기존 endpoint 재사용)
  - [x] 볼륨 목록 ActionMenu 스냅샷 생성 — `VolumeSnapshotModal.svelte` + `POST /api/volume-snapshots` (기존 endpoint 재사용)
  - [x] 사용자용 볼륨 용량 확장 — `POST /api/volumes/{id}/extend` + `cinder.extend_volume` + `VolumeExtendModal.svelte` (available + in-use 모두 허용, 단위 테스트 7건)

- [x] 5.4 VM 스케일링 지원
  - [x] 인스턴스 resize (플레이버 변경) — `POST /api/admin/instances/{id}/resize`, `/revert-resize` 엔드포인트 + `nova.resize_server`/`revert_resize_server` 서비스 함수 추가. `InstanceDetailPanel`에 resize 모달(flavor 선택) + VERIFY_RESIZE 상태에서 '되돌리기' 버튼 추가. 단위 테스트 4건 (`test_admin_resize.py`)
  - [x] 인스턴스 resize 시 OverlayFS 마운트 유지 검증 (통합 테스트) — `tests/integration/test_resize_overlay.py`. 19항 참조 (placeholder 제거 + SSH 직접 검증 + FIP 자동 할당)
  - [x] 다중 VM 동시 부팅 시 NFS share 동시 접근 안정성 검증 — `tests/integration/test_concurrent_boot.py`. 19항 참조 (병렬 SSH 마운트 검증)
  - [x] 라이선스/동시 접속 제한 검토 (상용 소프트웨어) — 11.2에서 `union_layers.create_mount` 가드 + 라이선스 필드 구현. 19항에서 DB 통합 회귀 테스트 4건(`test_libraries_license_db.py`) 추가

- [x] 5.5 보안 강화
  - [x] NFS export 옵션 보안: `root_squash`, `sec=sys` vs `sec=krb5` — `_build_nfs_access_metadata` + `create_access_rule(metadata=)` + `ensure_nfs_access_rule(root_squash, sec_flavor)` + 설정값 2개(`manila_nfs_root_squash`, `manila_nfs_sec_flavor`) + 단위테스트 13건
  - [x] CephX 키 로테이션 지원 — `rotate_cephx_access_rule` + `POST /api/instances/{id}/credentials/rotate-cephx` + systemd 타이머
  - [x] VM 간 데이터 격리 검증 (다른 프로젝트의 share 접근 차단) — `union_project_id` 메타 + list/get 필터
  - [x] NFS 방화벽 규칙 자동 관리 (Security Group) — `ensure_union_egress_sg` + instances.py auto-attach

- [x] 5.6 로깅 및 감사
  - [x] 마운트/언마운트 이벤트 로깅 (envmgr-use.sh → `POST /api/union/mounts` Bearer 토큰 통합, best-effort)
  - [x] 라이브러리 사용 통계 (Nova metadata `union_libraries` + `union_user_mounts` 활성 마운트 집계, 10분 시계열 스냅샷)
  - [x] 관리자 대시보드에 라이브러리 사용량 차트 추가 (`LibraryUsageChart.svelte`, 관리자 라이브러리 페이지 상단)

---

