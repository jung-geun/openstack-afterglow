## 관리자 인스턴스 자격 증명 관리

### 런타임 패스워드 재설정 (QEMU Guest Agent 기반)

- [x] `backend/app/services/nova.py` — `change_server_password(conn, server_id, password)`: Nova `changePassword` action 호출 (libvirt+QGA 게스트 비밀번호 변경)
- [x] `backend/app/services/nova.py` — `get_server_image_meta(conn, server_id)`: 이미지 QGA 지원 여부(`hw_qemu_guest_agent`) + `os_admin_user` 메타 조회. 볼륨 부팅 인스턴스는 cinder `volume_image_metadata` fallback
- [x] `backend/app/models/compute.py` — `AdminPasswordRequest`, `AdminPasswordPrecheck` Pydantic 모델 추가
- [x] `backend/app/api/compute/instances.py` — `GET /{server_id}/admin-password/precheck` (관리자 전용, QGA/상태 사전 점검)
- [x] `backend/app/api/compute/instances.py` — `POST /{server_id}/admin-password` (관리자 전용, ACTIVE + QGA 검증 후 변경, audit 로그 출력)
- [x] `backend/tests/test_instance_password.py` — 9케이스 단위 테스트 (403/404/409/422/204 검증)
- [x] `frontend/src/lib/components/InstanceDetailPanel.svelte` — admin-only "비밀번호 재설정" 버튼 + precheck 자동 호출 + 인라인 모달 (QGA 경고, os_admin_user 표시)

### 런타임 SSH 키 주입 정책

- [x] 표준 OpenStack은 실행 중 SSH 키 주입을 미지원 — 정책상 런타임 주입 기능 미구현
- [x] `InstanceDetailPanel.svelte` 패스워드 모달 내에 SSH 키 안내 문구 + 키페어 관리 링크 + rebuild 안내 추가

### GPU 인스턴스 DCGM Exporter 자동 설치 (cloud-init)

- [x] `backend/app/templates/cloudinit_base.yaml.j2` — `gpu_available=true` 시 설치 스크립트 + systemd unit 자동 생성 (네이티브 바이너리, `0.0.0.0:9400`)
- [x] `backend/app/services/cloudinit.py` — `_DCGM_EXPORTER_VERSION` 핀 상수 추가, 템플릿 렌더에 버전 전달
- [x] `backend/tests/test_cloudinit.py` — GPU/non-GPU 분기 3케이스 추가
- [x] **GPU 스택 풀-스택 idempotent 설치** (베이스 이미지 무관): `install_dcgm_exporter.sh` 에 ① `nvidia-smi` 미발견 시 `ubuntu-drivers autoinstall`, ② `nvidia-dcgm.service` 미발견 시 CUDA repo (`cuda-keyring`) 등록 + `datacenter-gpu-manager` 설치, ③ dcgm-exporter 바이너리 다운로드 단계 추가. `dcgm-exporter.service` 의 `Requires=nvidia-dcgm.service` 추가로 데몬 부팅 후 exporter 기동 보장. `test_cloudinit.py` 에 드라이버/DCGM 데몬 자동 설치 + systemd 의존성 검증 2건 추가
- [→] 보안 그룹 9400/tcp 자동 허용 — 12.2에서 통합 처리
- [→] Prometheus 스크래핑 대상 자동 등록 — 12.3/12.4에서 통합 처리


