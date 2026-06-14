## 31. 기존 부팅 볼륨에서 VM 부팅 (2026-05-12)

### 31.1 동기

부팅 가능한(`bootable=true`) Cinder 볼륨을 루트 디스크로 재사용해 VM을 생성하는 기능 추가.
기존엔 항상 이미지→볼륨 변환을 거쳐야 했으나, 스냅샷/백업으로 만든 부팅 볼륨을 직접 지정하면
이미지 변환 시간 없이 즉시 인스턴스를 생성할 수 있다.

### 31.2 백엔드

- [x] `backend/app/models/storage.py` — `VolumeInfo`에 `bootable: bool = False`, `volume_image_metadata: dict | None = None` 필드 추가
- [x] `backend/app/services/cinder.py` — `_vol_to_info`: bootable str→bool 정규화, volume_image_metadata 추출
- [x] `backend/app/models/compute.py` — `CreateInstanceRequest`: `image_id` optional화, `boot_volume_id: str | None` 추가, `model_validator`로 상호배타 검증
- [x] `backend/app/api/compute/instances.py` — step 2 분기: `boot_volume_id` 지정 시 `create_volume_from_image` 건너뜀, `available`/`bootable` 검증, rollback 시 제공된 볼륨 보호
- [x] `backend/tests/test_instance_boot_from_volume.py` (신규) — 6개 테스트: create_img_not_called, delete_on_termination_forced_false, 동시지정 422, 미지정 422, in-use 400, non-bootable 400

### 31.3 프런트엔드

- [x] `frontend/src/lib/types/resources.ts` — `Volume` 인터페이스에 `bootable?: boolean`, `volume_image_metadata?: Record<string, string> | null` 추가
- [x] `frontend/src/lib/stores/wizard.ts` — `WizardState`에 `bootSource: 'image' | 'volume'`, `bootVolumeId`, `bootVolumeName` 추가
- [x] `frontend/src/routes/dashboard/volumes/+page.svelte` — 부트 badge `vol.bootable` 기반으로 교체 + OS 정보 표시, ActionMenu에 "이 볼륨으로 VM 부팅" 항목 추가
- [x] `frontend/src/lib/components/VmCreatePanel.svelte` — Step 1: 이미지/기존 볼륨 토글, Step 5: bootSource=volume 시 루트 디스크 섹션 숨김, Step 6: 부트 소스 조건부 표시, deploy(): `boot_volume_id` 전송

### 31.4 검증

- [x] `npm run test:backend` 통과
- 사용자 검증 필요:
  - bootable 볼륨에서 ActionMenu "이 볼륨으로 VM 부팅" → 위저드 Step 1이 '기존 부팅 볼륨' 탭으로 열리고 해당 볼륨 선택 상태
  - 위저드에서 VM 생성 완료 → `POST /api/instances/async` 바디에 `boot_volume_id` 포함, `image_id` 없음
  - non-bootable / in-use 볼륨: ActionMenu 항목 미노출

---

