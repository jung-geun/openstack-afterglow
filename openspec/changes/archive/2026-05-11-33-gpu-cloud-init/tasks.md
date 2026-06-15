## 29. 콘솔 로그 전체 페이지 + GPU cloud-init 회귀 테스트 (2026-05-11)

### 29.1 동기

- **콘솔 로그 일부만 표시** — `InstanceDetailPanel` 의 콘솔 로그 패널은 length 200/10000줄 까지만. Horizon 처럼 새 탭에서 전체 콘솔 출력을 보고 싶다는 요청.
- **GPU 인스턴스 cloud-init 미실행 의심** — `gpu.1080ti_8c_16g` flavor 인스턴스 생성 후 GPU 메트릭 부재. 백엔드 진단 결과 `flavor.is_gpu` → True → `gpu_available=True` → `cloudinit_base.yaml.j2` 의 GPU 분기(install_dcgm_exporter.sh + dcgm-exporter.service) 활성화되어야 정상. 회귀 테스트로 backend 단의 user-data 정상 생성을 보장하고, 실제 진단은 사용자가 새로운 전체 로그 페이지로 검증.

### 29.2 백엔드

- [x] `api/compute/instances.py:get_console_log` — `length` 상한 `le=10000` → `le=100000`. 100k 라인까지 fetch 가능.
- [x] `tests/test_cloudinit_gpu.py` 신규 — `generate_userdata(gpu_available=True)` 결과 base64 디코드 후 검증:
  - `install_dcgm_exporter.sh` write_files 포함
  - `ubuntu-drivers autoinstall` 명령 포함
  - runcmd 에 `dcgm-exporter.service` enable 항목 포함
  - dcgm-exporter systemd unit 파일 + ExecStart 0.0.0.0:9400
  - CUDA_HOME export 포함
  - gpu_available=False 시 모든 GPU 항목 부재 (회귀 방지)

### 29.3 프런트엔드

- [x] `routes/dashboard/compute/instances/[id]/console-log/+page.svelte` 신규 — 풀스크린 로그 뷰어:
  - 검정 배경, monospace, ANSI escape raw 표시
  - sticky 상단 바: 인스턴스 ID, 새로고침/닫기 버튼, 마지막 로드 시간
  - `length=100000` 1회 fetch (자동 갱신 없음 — 큰 payload polling 회피, 사용자가 수동 새로고침)
  - `<svelte:head>` title 인스턴스 prefix
- [x] `lib/components/InstanceDetailPanel.svelte` — 콘솔 로그 패널에 "새 창에서 보기 ↗" 링크 추가 (`target="_blank"`).

### 29.4 검증

- [x] 백엔드 1338 → 1343 테스트 통과 (+5), lint/format 통과
- [x] 프런트엔드 타입 체크 통과
- 사용자 검증 필요:
  - 인스턴스 상세 → 콘솔 로그 → "새 창에서 보기 ↗" 클릭 → 풀스크린 페이지 표시
  - GPU 인스턴스에서 NVIDIA 설치 라인(`[gpu-install] NVIDIA 드라이버 미발견`) 새 페이지에서 확인 가능

### 29.5 후속 fix: GPU only 인스턴스의 user-data 누락 (2026-05-11)

**Root cause 확정**: 사용자가 전체 콘솔 로그를 공유 → cloud-init 이 130초만에 정상 완료했지만 NVIDIA 설치 단계 0건. `Frontend VmCreatePanel.svelte:291` 가 `/api/instances/async` 호출 → `instances.py:564` 의 `if resolved_libs:` 분기 안에서만 `cloudinit.generate_userdata()` 호출 → libraries=[] + GPU flavor 인스턴스는 **user-data 없이 부팅** → cloud-init 의 default cloud config 만 실행되고 NVIDIA 드라이버 미설치.

(동기 `create_instance` 핸들러 line 282 는 이 버그가 없음 — 항상 generate_userdata 호출. 하지만 frontend 가 `/async` 만 사용해서 노출됨.)

- [x] `api/compute/instances.py::create_instance_async` — cloud-init 생성 분기를 `if resolved_libs:` → `if resolved_libs or gpu_available:` 로 변경. Upper volume / Manila step 은 기존대로 `if resolved_libs:` 유지 (GPU only 인스턴스에는 불필요).
- [x] `tests/test_cloudinit_gpu.py::test_async_handler_generates_userdata_for_gpu_only_instance` — 분기 진리표 회귀 테스트 (4 케이스: libraries × GPU 조합).
- [x] 검증 안전성: `overlay_setup.sh` (set -euo pipefail) 는 systemd unit `union-overlay.service` 안에서만 실행 → mount 실패 해도 cloud-init runcmd 의 `/opt/union/install_dcgm_exporter.sh` 는 독립적으로 실행됨.
- [x] Nova create — `upper_volume_id=None` 일 때 attach skip (line 696 `if upper_volume_id:`).

### 29.6 사용자 작업 — 기존 인스턴스 NVIDIA 드라이버 설치

코드 fix 는 **신규 인스턴스부터 적용**. 기존 `test-nvidia-driver` 등 이미 만든 GPU 인스턴스에는 user-data 가 비어있어 자동 설치 안 됨. 두 옵션:

1. **인스턴스 재생성** — 가장 깔끔. 백엔드 재배포 후 동일 spec 으로 새로 생성.
2. **SSH 후 수동 설치**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y ubuntu-drivers-common
   sudo ubuntu-drivers autoinstall
   sudo reboot
   ```
   재부팅 후 `nvidia-smi` 로 확인. dcgm-exporter 가 필요하면 `cloudinit_base.yaml.j2` 의 install_dcgm_exporter.sh 내용을 참조해 수동 실행.

### 29.7 범위 외

- `ubuntu-drivers autoinstall` 이 1080ti(Pascal) 에 잘못된 드라이버 선택 가능성 — 신규 인스턴스 검증 후 문제 시 별도 PR.

---

