## 79. 보안 감사 및 표적 하드닝

> 전수 보안 감사(인증/인가/세션/IDOR · 인젝션 · 시크릿/암호화/설정/에러노출 · 프론트 XSS) 수행.
> 기존 컨트롤 대부분 견고함을 확인(fail-closed 토큰 바인딩, 해시 기반 timing-safe 토큰, AES-256-GCM+HKDF,
> project_id 소유권 스코프, shlex 쿼팅, CORS allowlist). 아래는 발견된 일관성 갭 5건의 표적 보완.

- [x] 79.1 cloud-init export 인젝션 방어 — `cloudinit.py` `_validate_export_path` + `_EXPORT_PATH_RE` 추가, `union_ro_share_export`/`union_manifest_share_export` 화이트리스트 검증(개행/따옴표/쉘 메타문자 거부 → YAML 구조 주입 차단). `tests/test_cloudinit.py` 인젝션 회귀 4종
- [x] 79.2 union `get_dependents` 소유권 우선 검증 — `api/union/layers.py` 부모 접근권 early return + 자식 cross-project 필터링. `tests/test_union_layers.py` IDOR 회귀 2종
- [x] 79.3 secret_key 엔트로피 게이트 — `config.py` 비기본이어도 32자 미만이면 production 부팅 거부(dev 경고). `tests/test_config_insecure_guard.py` 3종
- [x] 79.4 에러 응답 내부정보 노출 차단 — `api/common/errors.py` 5xx는 비관리자에게 일반 메시지로 치환(CLAUDE.md §6). `http_status`→`status_code` 속성 버그도 수정. `tests/test_errors.py` 6종
- [x] 79.5 `is_admin` 키 오타 수정 — `api/common/libraries.py` `is_admin`→`is_system_admin`(관리자가 카탈로그에서 private 라이브러리 조회 가능)
- 범위 외(향후): CSP `unsafe-inline` nonce 전환, JWT localStorage→HttpOnly 쿠키 전환
