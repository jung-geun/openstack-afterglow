## 11. VM 스케일링 + 보안 강화 (5.4 + 5.5 완성) — Milestone 11 ✅

> **완료**: resize 엔드투엔드(11.1), OverlayFS 검증 + 라이선스 가드(11.2), NFS 강화 + CephX 회전 + 3-share wiring(11.3), 프로젝트 격리 + Union SG 자동화(11.4) 전 항목 완료.

> **목표**: 미완료 상태로 남은 5.4(VM 스케일링) + 5.5(보안 강화) 항목을 4주 로드맵으로 완성

### 11.1 인스턴스 resize 엔드투엔드 (Week 1)

- [x] `backend/app/services/nova.py` — `resize_server()`, `revert_resize_server()` 추가
- [x] `backend/app/api/identity/admin.py` — `POST /api/admin/instances/{id}/resize`, `/revert-resize` 엔드포인트 추가 (관리자 전용, 캐시 무효화 포함)
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — ACTIVE/SHUTOFF 상태에서 "리사이즈" 버튼 + flavor select 모달, VERIFY_RESIZE 상태에서 "되돌리기" 버튼 추가
- [x] `backend/tests/test_admin_resize.py` — 신규 4건 (resize/revert 성공, 403 비관리자, nova 오류 400)

### 11.2 resize OverlayFS 검증 + 다중 VM 동시 부팅 + 라이선스 가드 (Week 2)

- [x] `backend/app/templates/overlay_setup.sh.j2` — jittered backoff (`RANDOM % 3`) 추가
- [x] `backend/tests/integration/test_concurrent_boot.py` — N=5 VM 동시 생성 → OverlayFS 마운트 검증 (slow marker, 실 인프라 skip)
- [x] `backend/tests/integration/test_resize_overlay.py` — resize → confirm → mountpoint 검증 (slow marker, 실 인프라 skip)
- [x] `backend/app/models/storage.py` + `db.py` — `LibraryConfig.license_type`, `max_concurrent_mounts` 필드 추가
- [x] `backend/app/services/union_layers.py:create_mount` — mount 한도 초과 시 409 가드
- [x] `backend/app/api/union/layers.py` — 두 필드 라우터 노출
- [x] `frontend/src/routes/admin/libraries/+page.svelte` — 라이선스 배지 + 활성 마운트 수 표시
- [x] `backend/tests/test_libraries.py` — license/max_concurrent_mounts 직렬화 단위 테스트 3건

### 11.3 NFS 옵션 강화 + CephX 회전 + 3-share wiring (Week 3)

- [x] `backend/app/api/compute/instances.py:1086` + `overlay_setup.sh.j2:28` — `nosuid,nodev,noexec` 추가
- [x] `scripts/envmgr-init.sh` — RO mount 옵션 통일 (`ro,nosuid,nodev,noexec,_netdev,noatime`)
- [x] `instances.py:1063` — `0.0.0.0/0` 폴백 제거 → vm_ip 미확보 시 503
- [x] `backend/app/services/manila.py` — `rotate_cephx_access_rule()` 헬퍼
- [x] `backend/app/api/compute/instance_health.py` — `POST /api/instances/{id}/credentials/rotate-cephx` 추가 (Bearer 토큰 인증)
- [x] `scripts/envmgr-rotate-key.sh` + systemd `union-rotate-key.timer` (신규, cloudinit_base.yaml.j2 통해 주입)
  - [x] **버그 수정**: `write_files`에 스크립트 미주입 → `envmgr_rotate_key.sh.j2` 템플릿 추가 + `cloudinit.py` 렌더링 + `cloudinit_base.yaml.j2` 주입 완료
- [x] `backend/app/api/union/layers.py` — `POST /api/union/user/access`, `DELETE /api/union/user/access/{access_id}` (3-share user wiring)
- [x] `backend/app/services/cloudinit.py` — `union_ro_share_export` 파라미터 + write_files 주입 (`LAYER_STORE_RO_EXPORT`)
- [x] `backend/app/config.py` — `union_cephx_rotate_hours: int = 24` 추가
- [x] `backend/tests/test_manila_rotate.py` — `rotate_cephx_access_rule` 단위 테스트 3건
- [x] `backend/tests/test_cloudinit.py` — `nosuid,nodev,noexec` + `LAYER_STORE_RO_EXPORT` 단위 테스트 2건 + rotate-key 주입 테스트 4건
- [x] `backend/tests/test_endpoint_inventory.py` — rotate-cephx 엔드포인트 whitelist 추가

### 11.4 격리 검증 + SG 자동화 (Week 4) ✅

- [x] `backend/app/services/manila.py` — `_parse_file_storage` `is_public` 추출, `list_file_storages` `caller_project_id` 필터 추가
- [x] `backend/app/models/storage.py` — `FileStorageInfo.is_public` 필드 추가
- [x] `backend/app/api/compute/instances.py:_prepare_dynamic_file_storage` — `union_project_id` 메타 자동 주입
- [x] `backend/app/services/library_builder.py` — prebuilt 빌드 완료 후 `set_share_public(True)` 자동 호출
- [x] `backend/app/api/storage/file_storage.py` — non-admin list `caller_project_id` 전달, GET cross-project private → 404
- [x] `backend/tests/integration/test_isolation.py` — 신규 3건 (`@pytest.mark.slow`, 실 인프라 skip 스켈레톤)
- [x] `backend/app/services/neutron.py` — `ensure_union_egress_sg()` idempotent 헬퍼 (NFS/CephFS/HTTP(S) 6 rule)
- [x] `backend/app/config.py` — `union_auto_egress_sg_enabled`, `union_egress_sg_name` 설정값 추가
- [x] `backend/app/api/compute/instances.py:create_instance` + `create_instance_async` — Union 사용 시 SG 자동 attach
- [x] `backend/tests/test_file_storage.py` — 격리 테스트 4건 (list 필터, public 노출, cross-project 404, admin 허용)
- [x] `backend/tests/test_manila_isolation.py` — `list_file_storages` caller_project_id 필터 단위 2건
- [x] `backend/tests/test_neutron.py` — `ensure_union_egress_sg` 3건 (미존재 생성+6룰, idempotent, 누락 룰만 추가)
- [x] `backend/tests/test_instances.py` — Union SG 자동 attach 2건 (auto-attach, disabled 시 미호출)


