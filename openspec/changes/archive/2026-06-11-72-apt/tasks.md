## 71. 라이브러리 레시피 모듈화 — 범용 빌딩 블록 + apt 스택 지원 (2026-06-11)

### 71.1 동기

기존 레시피는 라이브러리별 모놀리식 셸 문자열이었고, torch/vllm/jupyter는 Ubuntu 24.04에 없는
apt `python3.11`에 의존해 **빌드가 깨지는 상태**였다. apache+php 같은 시스템 패키지 스택을
레이어화할 메커니즘도 없었다. 어떤 라이브러리든 카탈로그+레시피 추가만으로 관리자 페이지에서
빌드 가능하도록 빌딩 블록 기반으로 모듈화한다.

### 71.2 구현

- [x] `app/services/recipe_blocks.py` (신규) — 조합 가능한 스크립트 블록:
  - `uv_bootstrap()` / `python_layer(ver)` / `pip_layer(pkgs, ver)` — uv 관리 CPython 기반 (apt python 의존 제거)
  - `apt_capture_layer(pkgs, debconf_selections=...)` — **범용 apt 캡처**: 루프백 ext4 upper(sparse)
    + `lowerdir=/` overlayfs + chroot apt 설치 → postinst 산출물 포함 전체 변경분을 캡처해 레이어로 병렬 복사.
    NFS는 overlayfs upperdir 불가·lowerdir 하위 경로는 overlap 제한이라 루프백 분리 FS 사용.
  - 모든 입력은 화이트리스트 정규식(Debian 패키지명/pip 스펙/debconf 라인) + `shlex.quote` 이중 방어
  - 공용 병렬 복사기(64스레드, whiteout 스킵, 권한·소유자 보존), `force-unsafe-io`(dpkg fsync 생략, 설치 후 제거)
- [x] `app/services/library_recipes.py` 재작성 — 블록 조합 선언 + `(library_id, version)` 멱등 seed:
  python311 v3, torch/vllm/jupyter v2(apt python3.11 제거), apache-php v1(신규), pytorch alias
- [x] `app/services/libraries.py` — 카탈로그에 `apache-php`(Apache + PHP + phpMyAdmin) 추가.
  관리자 페이지는 API에서 동적 로드하므로 자동 노출.
- [x] `cloud_init_builder.py` — 빌더 NFS 마운트에 `nconnect=8` (수만 파일 복사 RTT 병목 완화)
- [x] `tests/test_recipe_blocks.py` (신규 15건) — 블록 렌더·주입 방어·레시피 무결성·user_data 렌더 통합

### 71.3 라이브 검증 (apache-php 빌드, 2026-06-11)

- [x] **빌드 파이프라인 end-to-end 성공**: `POST /api/admin/libraries/build {library_id: apache-php}`
  → 빌더 VM에서 chroot apt 설치(apache2·php·phpmyadmin + 의존 60+패키지) → upper 캡처 → NFS 복사
  → `.union_build_complete` 플래그 ✓ (share `2077c200`)
- [x] **consumer 검증** (콘솔 sentinel 방식): RO+noexec 마운트 + overlayfs 구성 후
  `LD_LIBRARY_PATH=$ML/usr/lib/x86_64-linux-gnu` 지정 시 **`Apache/2.4.58` 실행 ✓, `PHP 8.3.6` 실행 ✓**,
  libaprutil·phpmyadmin·/etc/apache2 모두 레이어에 존재 ✓
- 발견 1 (소비 가이드): FHS 절대경로 가정 시스템 스택은 merged 서브트리 노출 특성상
  `LD_LIBRARY_PATH` 지정 또는 chroot/nspawn 소비가 필요. `/usr/bin/php` 같은
  `/etc/alternatives` 절대경로 심볼릭 링크는 호스트 루트를 가리켜 깨짐(직접 바이너리 `php8.3`은 정상).
  union-env.sh의 LD_LIBRARY_PATH에 `merged/usr/lib/<triplet>` 추가는 후속 작업.
- 발견 2 (1차 빌드 실패 원인): dpkg fsync로 apt 단계가 ~50분 지속되는 동안 빌더의 NFS RW 세션이
  wedge되어 이후 `/mnt/share` 접근이 hard mount에서 영구 블록 → `force-unsafe-io`로 설치를 수 분대로
  단축해 노출 최소화 (2차 빌드는 자력 완주).
- 미완: share `2077c200`의 prebuilt 승격(메타데이터 ready + 공개)은 수동 수행 필요 —
  로컬 하네스의 오케스트레이터가 VPN DNS 단절로 종료되어 `_handle_success` 미실행
  (프로덕션 상주 백엔드에서는 발생하지 않는 하네스 한계). 관리자 페이지 재빌드로도 대체 가능.

