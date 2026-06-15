## 19. 통합 테스트 보강 (2026-05-10) — 5.4 + 9.2 마지막 미완료 항목 마감

> **배경**: 11.5 Phase D에서 통합 테스트 스켈레톤은 `pytest.skip` 제거 단계까지 진행됐으나, 본문이 `image_id="placeholder"` / `flavor_id="placeholder"` 더미 값으로 작성되어 실 OpenStack 셀프호스티드 러너에서도 401/404로 즉시 실패. OverlayFS 마운트 검증도 health endpoint의 `mount_ok` 한 비트에만 의존해 agent 거짓 보고를 잡지 못함. 9.2 Builder→User VM 통합 테스트는 부재.

### 19.1 DELETE 템플릿 엔드포인트 + 서비스 함수 신규

- [x] `backend/app/services/union_layers.py` — `delete_template(session, name, version)` 추가 (멱등, 미존재 시 False)
- [x] `backend/app/api/union/layers.py` — `DELETE /api/union/templates/{name}/{version}` 관리자 전용 라우터 추가 (404 분기 + activity log)
- [x] `backend/tests/test_union_layers.py` — 단위 테스트 4건 (admin 정상 204 / 404 / 비관리자 403 / 서비스 멱등 False)

### 19.2 SSH 검증 헬퍼

- [x] `backend/tests/integration/ssh_helper.py` — 신규. `wait_for_ssh`, `ssh_run`, `verify_overlay_mount`, `verify_nfs_mounts`, `verify_envmgr_status`. subprocess(ssh) 기반(paramiko 미도입), `BatchMode=yes` + `StrictHostKeyChecking=no` + `UserKnownHostsFile=/dev/null` 공통 옵션

### 19.3 통합 테스트 본문 정합성 (5.4)

- [x] `backend/tests/integration/conftest.py` — `IntegrationResources` dataclass + `integration_resources` 픽스처 추가 (env 기반, 누락 시 자동 skip, SSH 키 chmod 600 자동)
- [x] `backend/tests/integration/test_resize_overlay.py` — placeholder 제거, FIP 자동 할당, SSH로 사전·사후 OverlayFS 검증 (12단계)
- [x] `backend/tests/integration/test_concurrent_boot.py` — placeholder 제거, FIP 동시 할당, 병렬 SSH 마운트 검증, health 이중 검증

### 19.4 Union v2 엔드투엔드 통합 테스트 (9.2)

- [x] `backend/tests/integration/test_union_e2e.py` — Builder→seal→fork→template→user mount→409 가드→unmount→cleanup 13단계. manila + RW/RO share 미설정 환경에서는 builder/user access 단계만 조건부 skip하고 핵심 흐름은 항상 검증

### 19.5 라이선스/동시 마운트 가드 회귀 테스트 (5.4)

- [x] `backend/tests/test_libraries_license_db.py` — 신규 4건 (`@pytest.mark.db`):
  - `commercial + max=2` → 첫 두 mount 성공, 세 번째 409
  - unmount 후 슬롯 회수 → 새 mount 성공
  - `open + max=NULL` → 10건 동시 mount 무제한
  - `commercial + max=0` → 모든 mount 즉시 409
- 11.5 Phase C MariaDB 11.4 인프라 재사용. `test_union_layers_db.py`와 동일 fixture 패턴

### 19.6 CI workflow 통합

- [x] `.github/workflows/test.yml::test-backend-integration` — 6개 신규 env 노출:
  - `AFTERGLOW_TEST_IMAGE_ID`, `AFTERGLOW_TEST_FLAVOR_SMALL`, `AFTERGLOW_TEST_FLAVOR_MEDIUM` (secrets)
  - `AFTERGLOW_TEST_SSH_KEY` (secrets)
  - `AFTERGLOW_TEST_LIBRARY_IDS`, `AFTERGLOW_TEST_SSH_USER` (vars)
- secrets/vars 미설정 시 픽스처에서 자동 skip → CI 차단 없음. 등록은 GitHub UI에서 별도 작업

### 19.7 검증 요약

```bash
# 로컬 단위 (즉시 검증 가능)
cd backend && uv run pytest tests/test_union_layers.py -v -k "delete_template"  # 4 passed

# DB 통합 (MariaDB profile=test 컨테이너 필요)
docker compose --profile test up -d mariadb
AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://... uv run pytest tests/test_libraries_license_db.py -m db

# 실 인프라 (셀프호스티드 러너 — 사용자 환경에서 1회 검증)
AFTERGLOW_ALLOW_INSECURE=1 AFTERGLOW_TEST_IMAGE_ID=<uuid> ... \
  uv run pytest tests/integration/test_resize_overlay.py tests/integration/test_concurrent_boot.py tests/integration/test_union_e2e.py -m slow
```

