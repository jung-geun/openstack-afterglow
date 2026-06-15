## § 40 — Drover Cluster Template CRUD (Magnum ClusterTemplate 도입)

**동기**: 사용자가 매번 k3s_version, agent_count, flavor, plugins를 직접 고르는 불편을 해소하고, 운영자가 표준 프리셋("GPU dev 3대 + Cinder CSI")을 정의해 사용자가 선택+override할 수 있는 Magnum ClusterTemplate 추상화 도입.

### 40.1 변경 파일

| 파일 | 변경 |
|---|---|
| `backend/app/models/db.py` | `K3sClusterTemplate` ORM 신규, `K3sCluster`에 `template_id`/`template_snapshot` 컬럼 추가 |
| `backend/app/models/k3s.py` | `K3sClusterTemplateInfo`, `CreateK3sClusterTemplateRequest`, `UpdateK3sClusterTemplateRequest` Pydantic 모델 신규, `CreateK3sClusterRequest.template_id` 추가 |
| `backend/app/services/k3s_template.py` (신규) | CRUD 서비스 (soft-delete, 권한 분기: admin=All / user=public+own) |
| `backend/app/api/k3s/templates.py` (신규) | GET 목록/단건, admin POST/PATCH/DELETE 5개 엔드포인트 |
| `backend/app/api/k3s/__init__.py` | `k3s_templates_router` export |
| `backend/app/main.py` | `k3s_templates_router` 등록 (`service_k3s_enabled` 가드 하위) |
| `backend/app/api/k3s/clusters.py` | `create_k3s_cluster_async`에 `_apply_template()` 머지 (요청 본문 값 우선) |
| `backend/app/services/k3s_db.py` | `_cluster_to_dict` / `create_cluster_record`에 template 필드 추가 |
| `backend/app/api/identity/admin.py` | `GET /admin/k3s-cluster-templates` 미러 엔드포인트 |
| `backend/migrations/009_k3s_cluster_templates.sql` (신규) | `k3s_cluster_templates` 테이블 DDL + `k3s_clusters` ALTER |
| `backend/tests/test_k3s_cluster_templates.py` (신규) | 15개 테스트 |
| `frontend/src/lib/types/k3s.ts` | `K3sClusterTemplate` 인터페이스 추가 |
| `frontend/src/lib/components/admin/drover/K3sClusterTemplateModal.svelte` (신규) | 생성/편집 모달 |
| `frontend/src/lib/components/admin/drover/K3sClusterTemplateCard.svelte` (신규) | 카드 컴포넌트 |
| `frontend/src/routes/admin/drover/templates/+page.svelte` (신규) | admin 전용 템플릿 관리 페이지 |
| `frontend/src/lib/components/dashboard/drover/K3sCreateClusterModal.svelte` | 템플릿 드롭다운 추가 + `applyTemplate()` |
| `frontend/src/routes/dashboard/drover/+page.svelte` | `createCluster`에 `template_id` 전달 |
| `frontend/src/lib/components/AdminSidebar.svelte` | "클러스터 템플릿" 메뉴 항목 추가 |

### 40.2 검증

- [x] 백엔드 15개 테스트 통과 (`test_k3s_cluster_templates.py`)
- [x] 기존 87개 테스트 회귀 없음
- [x] `ruff check` + `ruff format` — 수정 파일 통과
- [x] frontend svelte-check ERROR 없음 (a11y WARNING은 기존 패턴과 동일)
- [ ] 실 환경: admin 페이지에서 템플릿 생성 → 사용자 생성 모달 드롭다운 확인
- [ ] 실 환경: 템플릿 선택 후 agent_count/flavor override 동작 확인
- [ ] 실 환경: `public_visible=false` 템플릿이 타 사용자 드롭다운에 미노출 확인
- [ ] 실 환경: 템플릿 PATCH/DELETE 후 기존 클러스터 `template_snapshot` 보존 확인

---

