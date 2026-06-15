## 4. Cinder 볼륨 마이그레이션 (프로젝트 간)

> **목표**: 프로젝트 간 볼륨 이전 기능 ( Cinder volume transfer )

- [x] 4.1 Cinder 볼륨 Transfer API 연동
  - [x] `backend/app/services/cinder.py` — Transfer 관련 함수 추가:
    - [x] `create_volume_transfer()` — 볼륨 이전 생성 (auth token 포함)
    - [x] `accept_volume_transfer()` — 볼륨 이전 수락
    - [x] `list_volume_transfers()` — 이전 목록 조회
    - [x] `delete_volume_transfer()` — 이전 취소
  - [x] VM에 연결된 볼륨은 마이그레이션 전 detach 필요 — `POST /api/volumes/{id}/transfer` 자동 detach + `cinder.wait_volume_available` 대기 + transfer 실패 시 rollback attach 구현. 단위테스트 9건(`test_volume_transfer.py`)

- [x] 4.2 API 엔드포인트
  - [x] `POST /api/volumes/{id}/transfer` — 이전 생성
  - [x] `POST /api/volumes/transfer/{transfer_id}/accept` — 이전 수락
  - [x] `GET /api/volumes/transfers` — 이전 목록
  - [x] `DELETE /api/volumes/transfer/{transfer_id}` — 이전 취소

- [x] 4.3 Frontend — 볼륨 마이그레이션 UI
  - [x] 볼륨 목록 `available` 상태 행에 "이전" 버튼 추가
  - [x] `VolumeTransferModal.svelte` — 이전 생성(auth_key 복사)/수락(transfer_id+auth_key)/목록+취소
  - [x] `cinder.py` Transfer 서비스 함수 4개 구현 (이전에 누락되어 런타임 500 발생하던 버그 수정)

---

