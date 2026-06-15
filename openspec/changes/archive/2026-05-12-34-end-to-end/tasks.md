## 30. 라이브러리 빌더 안정화 — end-to-end 동작 확정 (2026-05-12)

### 30.1 동기

라이브러리 빌드 파이프라인(library_builder.py prebuilt share 트랙)을 실 환경에서 end-to-end 동작 가능 상태로 만든다.
진단된 이슈 3건:
1. 유저 VM cloud-init runcmd `mkdir -p /opt/layers/{lower,upper,work,merged}` — Ubuntu `/bin/sh`(dash)는 brace expansion 미지원 → literal 디렉토리 생성, union-overlay.service 실패.
2. 빌더 VM vdb 50GB 블록 디바이스 정체 (flavor ephemeral 의심, OpenStack CLI 검증 대기).
3. prebuilt share end-to-end (빌드 → probe VERIFY_OK → 메타데이터 갱신) 미검증.

### 30.2 백엔드

- [x] `backend/app/templates/cloudinit_base.yaml.j2:246` — runcmd mkdir brace expansion fix:
  `mkdir -p /opt/layers/{lower,upper,work,merged}` → 4개 개별 인자로 분리
  (dash `/bin/sh` 호환, bash brace expansion 의존 제거)
- [x] `backend/tests/test_cloudinit_dirs.py` (신규) — brace expansion 회귀 테스트 3건:
  - runcmd mkdir 라인에 `{`/`}` 없음
  - 4개 디렉토리(`lower`/`upper`/`work`/`merged`) 모두 포함
  - file_storages 있어도 동일

### 30.3 진단 대기 (사용자 OpenStack CLI 결과 수신 후 Phase C 분기 결정)

```bash
# vdb 정체 확정
openstack flavor show b9d8422a-ef0a-47e5-9e55-3cb01c7f0d68 -c disk -c ephemeral -c swap -c ram -c vcpus
# 빌더 VM 빌드 로그
openstack console log show union-builder-python311 | tail -200
# 유저 VM union-overlay 실패 원인
sudo cat /var/log/union-overlay.log && ls /opt/layers/
```

### 30.4 검증

- [x] `npm run test:backend` 1369 passed (0 failed), lint 통과
- 사용자 검증 필요:
  - 신규 VM 생성 → `ls /opt/layers/` 에 literal `{...}` 없음
  - `mount | grep overlay` 에서 `/opt/layers/merged` 확인
  - `python3.11 -c "import sys; print(sys.path)"` 에 `/opt/layers/merged/...` 포함

### 30.3 추가 버그 수정 (코드 분석)

- [x] `backend/app/services/library_builder.py`
  - `_monitor_build:length=200` → `length=2000`: 콘솔 로그 잘림으로 성공 빌드를 실패 오판하는 CRITICAL 버그
  - `_cleanup_builder_resources` 헬퍼 추출: ERROR/타임아웃 케이스 공통 정리 (share metadata + builder CephX rule revoke + VM 삭제). 기존엔 access rule이 정리 안 돼 유령 CephX user 잔류.
- [x] `backend/app/services/manila.py`
  - `_get_access_key`: 20회 재시도 후 빈 문자열 반환 → `RuntimeError` 발생. 빈 key가 cloud-init에 주입되면 CephFS 마운트가 반드시 실패하므로 호출부에서 인지 가능하게.
  - `_revoke_access_rule_raw` 헬퍼 추가: key 발급 타임아웃 시 `create_access_rule`이 고아 rule 자동 revoke 후 예외 재발생.

### 30.4 검증

- [x] `npm run test:backend` 1369 passed (0 failed)
- 사용자 검증 필요:
  - 신규 VM 생성 → `ls /opt/layers/` 에 literal `{...}` 없음
  - `mount | grep overlay` 에서 `/opt/layers/merged` 확인
  - `python3.11 -c "import sys; print(sys.path)"` 에 `/opt/layers/merged/...` 포함

### 30.5 범위 외

- 빌더 flavor 교체 (ephemeral=0) — Phase C-1: OpenStack CLI 결과 확인 후
- CephFS 마운트 실패 근본 원인 — Phase C-3: 유저 VM overlay 로그 분석 후

