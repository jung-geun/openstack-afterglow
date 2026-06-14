## 21. layerbuild CLI 검증 강화 (2026-05-10) — 9.1 Phase 1 안전망 도입

> **배경**: `scripts/layerbuild.py`(387라인)는 Builder VM에서 Union v2 레이어를 만드는 핵심 CLI. 9.1에서 코드는 [x] 완료지만 **단위 테스트 0건**, 9.1 인프라(Manila 3개 share + Builder VM)도 미설정 상태라 운영 검증 부재. 회귀를 잡을 안전망이 전혀 없었다.

### 21.1 `--dry-run` 글로벌 플래그 + `_run` helper

- [x] `scripts/layerbuild.py` — `_run(cmd, *, dry_run=False, ...)` 헬퍼로 모든 subprocess 호출 일원화. dry-run에서는 명령 트레이스(`$ mount --bind ...` 형태)만 출력, 실제 destructive 작업 미수행.
- [x] `_api_get` / `_api_post`도 dry-run 분기 추가 — stub 응답 반환.
- [x] `_compute_layer_hash`도 dry-run에서는 placeholder hash(`sha256:0...0`) 반환 (옵션 B — 흐름 트레이스가 본질, real hash는 단위 테스트로 검증).
- [x] dry-run 원칙: state file 미작성, mkdir 미수행 → **chainable 아님** (단일 명령 단위로만 동작). 사용자가 `init→exec→seal` 시퀀스를 미리 보려면 각 명령 독립 호출.
- [x] argparse에 `--dry-run` 글로벌 플래그 추가, 모든 cmd 함수가 `args.dry_run` 전달받음.

### 21.2 API 등록 실패 복구 — `.api_pending` 마커 + `cmd_resume_api`

- [x] `cmd_seal`이 API POST 예외 시 `dest_dir/.api_pending` 파일에 등록 payload(JSON) 저장. layer dir은 디스크에 이미 락 적용된 상태로 남아도 재시도 경로 확보.
- [x] 새 서브커맨드 `layerbuild resume-api <sha256:hash>` — `.api_pending` 읽고 POST 두 번 (등록 + 봉인) 재시도 → 성공 시 마커 삭제.
- [x] `_require_api_env()` 헬퍼로 환경변수 사전 검증 (cmd_init parent 지정 시, cmd_resume_api에서 호출).

### 21.3 단위 테스트 신규: `backend/tests/test_layerbuild.py` (21건)

- [x] **Pure 헬퍼 (5)**: state I/O 라운드트립, `_compute_layer_hash` 결정성/콘텐츠 변경 검출/빈 디렉토리/dry-run placeholder. **GNU tar(`--sort=name`) 미설치 환경(macOS BSD tar)에서는 hash 결정성 테스트 3건 자동 skip** — `_has_gnu_tar()` 가드.
- [x] **argparse (3)**: --version 필수 검증, 글로벌 --dry-run 파싱, resume-api 서브커맨드.
- [x] **cmd_init (5)**: parent 없을 때 bind mount + state 생성, parent 지정 시 `_api_get` 조상 체인 → lowerdir 조립 검증, state 충돌 시 exit 1, dry-run에서 mount/state 미생성, parent + API env 미설정 시 명확한 exit.
- [x] **cmd_seal (4)**: state 없으면 exit, API POST 두 번 순서 (`/api/union/layers` → `/api/union/layers/{id}/seal`), API 실패 시 `.api_pending` 마커 + content_hash 포함, dry-run 트레이스에 umount/chmod/chattr 포함.
- [x] **cmd_abort (2)**: state 없으면 조용히 종료, umount + work rmtree + state 클리어.
- [x] **cmd_resume_api (2)**: 마커 읽고 POST 두 번 → 마커 삭제, 마커 없으면 exit 1.
- [x] **결정성 보장 fixture**: `_normalize_dir(path)`가 모든 파일/디렉토리에 명시적 `chmod 0o644/0o755 + os.utime((0, 0))` 적용 → 환경 의존(umask, mtime) 제거.
- [x] **MagicMock 'parent' 속성 충돌 회피**: `argparse.Namespace` 사용 — MagicMock의 내부 `parent` 속성과 args.parent 충돌 방지.

### 21.4 검증

- [x] 백엔드 단위 테스트 1274건 그린 (1256 → 1274, +18 추가, 3건은 GNU tar 환경에서 추가 skip 해제 예정)
- [x] ruff check + format 통과
- [x] 수동 dry-run 검증: `python3 scripts/layerbuild.py --dry-run init test --version 1.0` → 명령 트레이스만 출력, 실제 mount/mkdir 미수행 확인

### 21.5 범위 외

- **Manila share 3개 실제 프로비저닝 + Builder VM 셋업** — 인프라 작업 (사용자 OpenStack 환경에서 수행). 본 plan 범위 외.
- **layerbuild fork/rebuild 새 서브커맨드** — Phase 3에 별도 항목.
- **GNU tar 의존을 Python `tarfile` 모듈로 분리** — cross-platform 가능하나 기존 GNU tar 동작과 정확히 일치한다는 보장이 어려움. 별도 PR.

