## 3. 사전 패키지(Pre-built Library) 관리 시스템

> **목표**: Admin 프로젝트에서 사전 빌드된 라이브러리 패키지(NFS share)를 생성하고, 다른 프로젝트에서도 read-only로 사용 가능하게 구현

- [x] 3.1 Admin 프로젝트 — 패키지 생성 API
  - [x] `POST /api/admin/libraries/build` — 라이브러리 패키지 빌드 트리거 (`auto_install` 옵션)
  - [x] 기존 `POST /api/admin/file-storage/build` 확장:
    - [x] `share_proto` 파라미터 추가 (CEPHFS / NFS 선택)
    - [x] 의존성 메타데이터 `union_depends_on` 필드 추가
    - [x] 빌드 상태 관리: `building` → `ready` / `failed` / `cancelled` 상태 전이, `cancel_build()` 구현
  - [x] `GET /api/admin/libraries` — 전체 프로젝트 가용 라이브러리 목록 (의존성 포함)
  - [x] `GET /api/admin/libraries/{id}` — 라이브러리 상세 (의존성 트리 포함)
  - [x] `GET /api/admin/libraries/builds` — 빌드 이력 목록 (DB + 인메모리 fallback)
  - [x] `POST /api/admin/libraries/builds/{id}/cancel` — 빌드 취소 (VM 정리 포함)
  - [x] `backend/app/api/identity/admin_libraries.py` — 전용 라우터 신규 구현 (관리자 인증 필수)

- [x] 3.2 Manila 메타데이터 기반 의존성 추적
  - [x] Manila share metadata 활용:
    ```json
    {
      "union_type": "prebuilt",
      "union_library": "vllm",
      "union_version": "0.6.0",
      "union_depends_on": "python311,torch",
      "union_python_version": "3.11",
      "union_ubuntu_versions": "22.04,24.04",
      "union_share_proto": "NFS",
      "union_status": "ready"
    }
    ```
  - [x] `LibraryConfig` 모델 확장: `share_proto`, `ubuntu_versions` 필드 추가
  - [x] 의존성 검증 로직: `validate_compatibility()`, `check_python_version_conflict()` — Ubuntu 버전 / Python 버전 충돌 감지. `POST /api/libraries/validate` 엔드포인트 추가

- [x] 3.3 크로스 프로젝트 접근 관리
  - [x] Admin 프로젝트에서 NFS share 생성 시 다른 프로젝트 접근 허용:
    - [x] Manila share를 `public` 으로 설정 (`is_public=True`) — `set_share_public()` API 구현
    - [x] VM 생성 시 해당 프로젝트의 네트워크 CIDR로 NFS access rule 자동 생성 — `_prepare_prebuilt_file_storages`에 NFS 분기 추가, service project conn으로 `ensure_nfs_access_rule` 호출
    - [x] `POST /api/admin/libraries/{id}/project-access` — 관리자 수동 CIDR grant (idempotent)
    - [x] `DELETE /api/admin/libraries/{id}/project-access/{project_id}` — 관리자 수동 revoke (`union_grant_project` metadata로 식별)
    - [x] `GET /api/admin/libraries/{id}/project-access` — 프로젝트별 grant 목록 조회
  - [x] CephFS의 경우: 기존 CephX access rule 방식 유지
  - [x] VM 삭제 cleanup: prebuilt cephx rule은 service conn으로 revoke, NFS CIDR rule은 lifecycle A(관리자 수동 revoke)
  - [x] `backend/app/services/libraries.py` — `get_dependency_tree()` 크로스 프로젝트 라이브러리 의존성 트리 조회 함수 추가

- [x] 3.4 패키지 빌드 파이프라인 개선
  - [x] `scripts/build_library_shares.py` 확장:
    - [x] NFS share 빌드 지원 (`--proto NFS` 옵션)
    - [x] 의존성 메타데이터 자동 기록
    - [x] 빌드 완료 후 자동 검증 (마운트 테스트) — probe VM (`_verify_layer_accessible`) VERIFY_OK/FAIL 판별 후 status=error 전환
  - [x] 백그라운드 빌드 워커: asyncio.Queue 기반 큐(`queue_build`/`_build_worker`/`get_build_queue_status`) + main.py 시작 시 워커 자동 실행

- [x] 3.5 Frontend — Admin 패키지 관리 UI
  - [x] `routes/admin/libraries/+page.svelte` — 라이브러리 카탈로그 관리 페이지 (카드 그리드)
  - [x] 패키지 빌드 상태 표시 (building / ready / failed / none)
  - [x] 빌드 트리거 버튼 + AutoRefresh (10초)
  - [x] 의존성 배지 표시
  - [x] 의존성 그래프 시각화 (SVG 연결선) — 레벨 기반 DAG, 빌드 상태 색상, 노드 클릭 스크롤
  - [x] 패키지 공개/비공개 설정 — `visibility` 필드 추가, non-admin은 public만 반환

- [x] 3.6 VM 생성 마법사 — 라이브러리 선택 개선
  - [x] 의존성 자동 해석: vllm 선택 시 torch, python311 자동 체크 (전이적 DFS 해결)
  - [x] 호환성 검증: Ubuntu 버전 / Python 버전 충돌 시 경고 (`POST /api/libraries/validate` 연동, debounce 300ms)
  - [x] 마운트 프로토콜 표시 (NFS / CephFS) — SelectLibraries.svelte에 이미 구현됨

---

