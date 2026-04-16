"""관리자 쓰기 엔드포인트 403 권한 분리 통합 테스트.

require_admin Depends가 body 파싱/리소스 조회보다 먼저 실행되므로
가짜 ID + 빈 body로 요청해도 실제 리소스 변경 없이 403 검증 가능.
"""

import pytest

# ---------------------------------------------------------------------------
# 관리자 쓰기 엔드포인트 목록 (method, path, body, label)
# ---------------------------------------------------------------------------

ADMIN_WRITE_ENDPOINTS = [
    # ── admin.py ──────────────────────────────────────────────────────────
    ("POST", "/api/admin/file-storage/build", {}, "admin-file-storage-build"),
    ("POST", "/api/admin/ports", {}, "admin-ports-create"),
    ("PATCH", "/api/admin/volumes/fake-volume-id", {}, "admin-volume-patch"),
    ("DELETE", "/api/admin/volumes/fake-volume-id", None, "admin-volume-delete"),
    ("POST", "/api/admin/volumes/fake-volume-id/extend", {}, "admin-volume-extend"),
    ("POST", "/api/admin/volumes/fake-volume-id/reset-status", {}, "admin-volume-reset-status"),
    ("POST", "/api/admin/volumes/fake-volume-id/transfer", {}, "admin-volume-transfer"),
    ("POST", "/api/admin/instances/fake-server-id/live-migrate", {}, "admin-live-migrate"),
    ("POST", "/api/admin/instances/fake-server-id/cold-migrate", {}, "admin-cold-migrate"),
    ("POST", "/api/admin/instances/fake-server-id/confirm-resize", {}, "admin-confirm-resize"),
    ("POST", "/api/admin/networks", {}, "admin-network-create"),
    ("PUT", "/api/admin/networks/fake-net-id", {}, "admin-network-update"),
    ("DELETE", "/api/admin/networks/fake-net-id", None, "admin-network-delete"),
    ("POST", "/api/admin/floating-ips", {}, "admin-fip-create"),
    ("DELETE", "/api/admin/floating-ips/fake-fip-id", None, "admin-fip-delete"),
    ("POST", "/api/admin/routers", {}, "admin-router-create"),
    ("PUT", "/api/admin/routers/fake-router-id", {}, "admin-router-update"),
    ("DELETE", "/api/admin/routers/fake-router-id", None, "admin-router-delete"),
    ("PUT", "/api/admin/ports/fake-port-id", {}, "admin-port-update"),
    ("DELETE", "/api/admin/ports/fake-port-id", None, "admin-port-delete"),
    ("DELETE", "/api/admin/k3s-clusters/fake-cluster-id", None, "admin-k3s-cluster-delete"),
    # ── admin_identity.py ─────────────────────────────────────────────────
    ("POST", "/api/admin/users", {}, "admin-user-create"),
    ("PATCH", "/api/admin/users/fake-user-id", {}, "admin-user-update"),
    ("POST", "/api/admin/projects", {}, "admin-project-create"),
    ("PATCH", "/api/admin/projects/fake-proj-id", {}, "admin-project-update"),
    ("DELETE", "/api/admin/projects/fake-proj-id", None, "admin-project-delete"),
    ("PUT", "/api/admin/quotas/fake-proj-id", {}, "admin-quota-update"),
    ("POST", "/api/admin/groups", {}, "admin-group-create"),
    ("PATCH", "/api/admin/groups/fake-grp-id", {}, "admin-group-update"),
    ("DELETE", "/api/admin/groups/fake-grp-id", None, "admin-group-delete"),
    ("PUT", "/api/admin/groups/fake-grp-id/users/fake-user-id", {}, "admin-group-add-user"),
    ("DELETE", "/api/admin/groups/fake-grp-id/users/fake-user-id", None, "admin-group-remove-user"),
    ("POST", "/api/admin/roles/assign", {}, "admin-role-assign"),
    ("DELETE", "/api/admin/roles/assign", None, "admin-role-unassign"),
    ("POST", "/api/admin/roles/assign-group", {}, "admin-role-assign-group"),
    ("DELETE", "/api/admin/roles/assign-group", None, "admin-role-unassign-group"),
    # ── admin_flavors.py ──────────────────────────────────────────────────
    ("POST", "/api/admin/flavors", {}, "admin-flavor-create"),
    ("DELETE", "/api/admin/flavors/fake-flavor-id", None, "admin-flavor-delete"),
    ("POST", "/api/admin/flavors/fake-flavor-id/extra-specs", {}, "admin-extra-specs-create"),
    ("DELETE", "/api/admin/flavors/fake-flavor-id/extra-specs/fake-key", None, "admin-extra-specs-delete"),
    ("POST", "/api/admin/flavors/fake-flavor-id/access", {}, "admin-flavor-access-add"),
    ("DELETE", "/api/admin/flavors/fake-flavor-id/access/fake-proj", None, "admin-flavor-access-remove"),
    # ── admin_images.py ───────────────────────────────────────────────────
    ("PATCH", "/api/admin/images/fake-img-id", {}, "admin-image-update"),
    ("DELETE", "/api/admin/images/fake-img-id", None, "admin-image-delete"),
    ("POST", "/api/admin/images/fake-img-id/deactivate", {}, "admin-image-deactivate"),
    ("POST", "/api/admin/images/fake-img-id/reactivate", {}, "admin-image-reactivate"),
    # ── admin_notion.py ───────────────────────────────────────────────────
    ("POST", "/api/admin/notion/config", {}, "admin-notion-config-save"),
    ("DELETE", "/api/admin/notion/config", None, "admin-notion-config-delete"),
    ("POST", "/api/admin/notion/test", {}, "admin-notion-test"),
]


@pytest.mark.parametrize(
    "method,path,body,label",
    ADMIN_WRITE_ENDPOINTS,
    ids=[ep[3] for ep in ADMIN_WRITE_ENDPOINTS],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_admin_write_forbidden_for_user(user_client, method, path, body, label):
    """일반 유저의 관리자 쓰기 요청은 require_admin에서 403으로 즉시 차단된다.

    가짜 ID + 빈 body를 사용하므로 실제 리소스 변경은 발생하지 않는다.
    Depends(require_admin)는 body 파싱보다 먼저 실행되므로 422가 아닌 403이 반환된다.
    """
    resp = await user_client.request(method, path, json=body)
    assert resp.status_code == 403, (
        f"{method} {path}: expected 403 (require_admin), got {resp.status_code}: {resp.text[:200]}"
    )
