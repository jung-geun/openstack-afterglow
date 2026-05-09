"""Admin Library project-access API 단위 테스트 (§3.3).

POST/DELETE/GET /api/admin/libraries/{id}/project-access 엔드포인트 커버.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.storage import FileStorageInfo
from tests.conftest import make_mock_conn, make_token_info

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_nfs_storage(share_id: str = "share-nfs-1", library_id: str = "python311") -> FileStorageInfo:
    return FileStorageInfo(
        id=share_id,
        name=f"union-prebuilt-{library_id}",
        status="available",
        size=20,
        share_proto="NFS",
        export_locations=["10.0.0.1:/exports/python311"],
        metadata={"union_type": "prebuilt", "union_library": library_id},
        project_id="svc-project-id",
        created_at="2025-01-01T00:00:00Z",
        nfs_export_location="10.0.0.1:/exports/python311",
        library_name=library_id,
        library_version="1.0",
        built_at="2025-01-01",
    )


def make_cephfs_storage(share_id: str = "share-ceph-1", library_id: str = "torch") -> FileStorageInfo:
    return FileStorageInfo(
        id=share_id,
        name=f"union-prebuilt-{library_id}",
        status="available",
        size=20,
        share_proto="CEPHFS",
        export_locations=[],
        metadata={"union_type": "prebuilt", "union_library": library_id},
        project_id="svc-project-id",
        created_at="2025-01-01T00:00:00Z",
        nfs_export_location=None,
        library_name=library_id,
        library_version="1.0",
        built_at="2025-01-01",
    )


def make_subnet_detail(cidr: str = "10.10.0.0/24"):
    s = MagicMock()
    s.cidr = cidr
    return s


def make_network_detail(cidr: str = "10.10.0.0/24"):
    nd = MagicMock()
    nd.subnet_details = [make_subnet_detail(cidr)]
    return nd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_conn():
    return make_mock_conn("admin-project-id")


@pytest.fixture
async def admin_client(mock_conn):
    from app.api.deps import get_os_conn, get_token_info

    async def override_token():
        return make_token_info(roles=["admin"], is_system_admin=True, project_id="admin-project-id")

    async def override_conn():
        yield mock_conn

    app.dependency_overrides[get_token_info] = override_token
    app.dependency_overrides[get_os_conn] = override_conn
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_token_info, None)
    app.dependency_overrides.pop(get_os_conn, None)


@pytest.fixture
async def user_client(mock_conn):
    from app.api.deps import get_os_conn, get_token_info

    async def override_token():
        return make_token_info(roles=["member"])

    async def override_conn():
        yield mock_conn

    app.dependency_overrides[get_token_info] = override_token
    app.dependency_overrides[get_os_conn] = override_conn
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_token_info, None)
    app.dependency_overrides.pop(get_os_conn, None)


# ---------------------------------------------------------------------------
# POST /api/admin/libraries/{id}/project-access
# ---------------------------------------------------------------------------


class TestGrantProjectAccess:
    @pytest.mark.asyncio
    async def test_grant_success(self, admin_client):
        """NFS 라이브러리에 프로젝트 CIDR access rule 추가 성공."""
        nfs_storage = make_nfs_storage()
        with (
            patch(
                "app.api.identity.admin_libraries.get_service_project_connection",
                return_value=MagicMock(),
            ),
            patch(
                "app.api.identity.admin_libraries.manila.list_file_storages",
                return_value=[nfs_storage],
            ),
            patch(
                "app.api.identity.admin_libraries.neutron.get_network_detail",
                return_value=make_network_detail("10.10.0.0/24"),
            ),
            patch(
                "app.api.identity.admin_libraries.manila.ensure_nfs_access_rule",
                return_value={
                    "access_id": "rule-new-1",
                    "access_key": "",
                    "access_to": "10.10.0.0/24",
                    "access_level": "ro",
                },
            ),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-b"
        assert "10.10.0.0/24" in data["granted_cidrs"]
        assert len(data["rules"]) == 1

    @pytest.mark.asyncio
    async def test_grant_idempotent(self, admin_client):
        """동일 요청 재호출 시 ensure_nfs_access_rule이 2회 호출되어도 오류 없음."""
        nfs_storage = make_nfs_storage()
        mock_ensure = MagicMock(
            return_value={"access_id": "rule-1", "access_key": "", "access_to": "10.10.0.0/24", "access_level": "ro"}
        )
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.neutron.get_network_detail", return_value=make_network_detail()),
            patch("app.api.identity.admin_libraries.manila.ensure_nfs_access_rule", mock_ensure),
        ):
            resp1 = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
            resp2 = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert mock_ensure.call_count == 2  # ensure가 2회 호출되어도 idempotent

    @pytest.mark.asyncio
    async def test_grant_non_nfs_returns_400(self, admin_client):
        """CephFS 라이브러리에 grant 시도 → 400."""
        ceph_storage = make_cephfs_storage(library_id="torch")
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[ceph_storage]),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/torch/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 400
        assert "NFS" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_grant_unknown_library_returns_404(self, admin_client):
        """존재하지 않는 라이브러리 → 404."""
        with patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()):
            resp = await admin_client.post(
                "/api/admin/libraries/nonexistent-lib/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_grant_non_admin_forbidden(self, user_client):
        """비관리자 → 403."""
        resp = await user_client.post(
            "/api/admin/libraries/python311/project-access",
            json={"project_id": "proj-b", "network_id": "net-b"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_grant_passes_union_grant_project_metadata(self, admin_client):
        """ensure_nfs_access_rule 호출 시 union_grant_project metadata가 전달되는지 검증."""
        nfs_storage = make_nfs_storage()
        mock_ensure = MagicMock(
            return_value={"access_id": "rule-1", "access_key": "", "access_to": "10.10.0.0/24", "access_level": "ro"}
        )
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.neutron.get_network_detail", return_value=make_network_detail()),
            patch("app.api.identity.admin_libraries.manila.ensure_nfs_access_rule", mock_ensure),
        ):
            await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-target", "network_id": "net-b"},
            )
        # extra_metadata 인자에 union_grant_project가 포함되어야 함
        call_args = mock_ensure.call_args
        all_args = list(call_args[0]) + list(call_args[1].values())
        assert any(isinstance(a, dict) and a.get("union_grant_project") == "proj-target" for a in all_args), (
            f"union_grant_project가 call args에 없음: {call_args}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/admin/libraries/{id}/project-access/{project_id}
# ---------------------------------------------------------------------------


class TestRevokeProjectAccess:
    @pytest.mark.asyncio
    async def test_revoke_success(self, admin_client):
        """특정 프로젝트의 rule만 revoke."""
        nfs_storage = make_nfs_storage()
        rules = [
            {
                "id": "rule-b-1",
                "access_type": "ip",
                "access_to": "10.10.0.0/24",
                "access_level": "ro",
                "metadata": {"union_grant_project": "proj-b"},
            },
            {
                "id": "rule-c-1",
                "access_type": "ip",
                "access_to": "10.20.0.0/24",
                "access_level": "ro",
                "metadata": {"union_grant_project": "proj-c"},
            },
        ]
        mock_revoke = MagicMock()
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.manila.list_access_rules", return_value=rules),
            patch("app.api.identity.admin_libraries.manila.revoke_access_rule", mock_revoke),
        ):
            resp = await admin_client.delete("/api/admin/libraries/python311/project-access/proj-b")
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked_count"] == 1
        assert "rule-b-1" in data["revoked_rule_ids"]
        # proj-c의 rule은 revoke되지 않아야 함
        revoked_args = [call[0][2] for call in mock_revoke.call_args_list]
        assert "rule-c-1" not in revoked_args

    @pytest.mark.asyncio
    async def test_revoke_no_matching_rules_returns_zero(self, admin_client):
        """해당 프로젝트의 rule이 없을 때 revoked_count=0 반환."""
        nfs_storage = make_nfs_storage()
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.manila.list_access_rules", return_value=[]),
            patch("app.api.identity.admin_libraries.manila.revoke_access_rule"),
        ):
            resp = await admin_client.delete("/api/admin/libraries/python311/project-access/proj-x")
        assert resp.status_code == 200
        assert resp.json()["revoked_count"] == 0

    @pytest.mark.asyncio
    async def test_revoke_non_admin_forbidden(self, user_client):
        """비관리자 → 403."""
        resp = await user_client.delete("/api/admin/libraries/python311/project-access/proj-b")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/admin/libraries/{id}/project-access
# ---------------------------------------------------------------------------


class TestListProjectAccess:
    @pytest.mark.asyncio
    async def test_list_returns_grouped_by_project(self, admin_client):
        """프로젝트별 grouping 결과 반환."""
        nfs_storage = make_nfs_storage()
        rules = [
            {
                "id": "rule-b-1",
                "access_type": "ip",
                "access_to": "10.10.0.0/24",
                "metadata": {"union_grant_project": "proj-b"},
            },
            {
                "id": "rule-b-2",
                "access_type": "ip",
                "access_to": "fd00::/64",
                "metadata": {"union_grant_project": "proj-b"},
            },
            {
                "id": "rule-c-1",
                "access_type": "ip",
                "access_to": "10.20.0.0/24",
                "metadata": {"union_grant_project": "proj-c"},
            },
        ]
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.manila.list_access_rules", return_value=rules),
        ):
            resp = await admin_client.get("/api/admin/libraries/python311/project-access")
        assert resp.status_code == 200
        data = resp.json()
        assert data["library_id"] == "python311"
        grants = {g["project_id"]: g for g in data["grants"]}
        assert "proj-b" in grants
        assert len(grants["proj-b"]["cidrs"]) == 2
        assert "proj-c" in grants
        assert len(grants["proj-c"]["cidrs"]) == 1

    @pytest.mark.asyncio
    async def test_list_non_admin_forbidden(self, user_client):
        """비관리자 → 403."""
        resp = await user_client.get("/api/admin/libraries/python311/project-access")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_legacy_rules_grouped_as_unknown(self, admin_client):
        """metadata가 없는 레거시 rule은 '__unknown__' 프로젝트로 그룹화."""
        nfs_storage = make_nfs_storage()
        rules = [
            {
                "id": "rule-legacy-1",
                "access_type": "ip",
                "access_to": "192.168.0.0/24",
                # metadata 없음 — 레거시 rule
            },
            {
                "id": "rule-modern-1",
                "access_type": "ip",
                "access_to": "10.10.0.0/24",
                "metadata": {"union_grant_project": "proj-b"},
            },
        ]
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.manila.list_access_rules", return_value=rules),
        ):
            resp = await admin_client.get("/api/admin/libraries/python311/project-access")
        assert resp.status_code == 200
        grants = {g["project_id"]: g for g in resp.json()["grants"]}
        assert "__unknown__" in grants
        assert "proj-b" in grants


# ---------------------------------------------------------------------------
# §3.3 Negative-path 보강
# ---------------------------------------------------------------------------


class TestGrantNegativePaths:
    @pytest.mark.asyncio
    async def test_grant_includes_ipv6_cidr(self, admin_client):
        """dual-stack 네트워크(IPv4 + IPv6)가 있을 때 ensure가 두 CIDR 모두에 호출된다."""
        nfs_storage = make_nfs_storage()
        mock_ensure = MagicMock(
            return_value={"access_id": "rule-1", "access_key": "", "access_to": "", "access_level": "ro"}
        )
        dual_stack_detail = MagicMock()
        dual_stack_detail.subnet_details = [make_subnet_detail("10.10.0.0/24"), make_subnet_detail("fd00::/64")]
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.neutron.get_network_detail", return_value=dual_stack_detail),
            patch("app.api.identity.admin_libraries.manila.ensure_nfs_access_rule", mock_ensure),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 200
        data = resp.json()
        granted_cidrs = data["granted_cidrs"]
        assert "10.10.0.0/24" in granted_cidrs
        assert "fd00::/64" in granted_cidrs
        assert mock_ensure.call_count == 2

    @pytest.mark.asyncio
    async def test_grant_network_has_no_valid_cidrs_returns_400(self, admin_client):
        """네트워크 subnet이 있지만 유효한 CIDR이 없는 경우 → 400."""
        nfs_storage = make_nfs_storage()
        empty_cidr_detail = MagicMock()
        empty_subnet = MagicMock()
        empty_subnet.cidr = None
        empty_cidr_detail.subnet_details = [empty_subnet]
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.neutron.get_network_detail", return_value=empty_cidr_detail),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 400
        assert "CIDR" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_grant_keystone_failure_returns_502(self, admin_client):
        """`get_service_project_connection` 예외 시 502."""
        with patch(
            "app.api.identity.admin_libraries.get_service_project_connection",
            side_effect=RuntimeError("Keystone 연결 불가"),
        ):
            resp = await admin_client.post(
                "/api/admin/libraries/python311/project-access",
                json={"project_id": "proj-b", "network_id": "net-b"},
            )
        assert resp.status_code == 502


class TestRevokeNegativePaths:
    @pytest.mark.asyncio
    async def test_revoke_skips_legacy_rules_without_metadata(self, admin_client):
        """metadata 없는 레거시 rule은 revoke 대상에서 제외된다."""
        nfs_storage = make_nfs_storage()
        mock_revoke = MagicMock()
        rules = [
            {
                "id": "rule-legacy",
                "access_type": "ip",
                "access_to": "192.168.0.0/24",
                # metadata 없음 — 레거시 rule
            },
            {
                "id": "rule-modern",
                "access_type": "ip",
                "access_to": "10.10.0.0/24",
                "metadata": {"union_grant_project": "proj-target"},
            },
        ]
        with (
            patch("app.api.identity.admin_libraries.get_service_project_connection", return_value=MagicMock()),
            patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[nfs_storage]),
            patch("app.api.identity.admin_libraries.manila.list_access_rules", return_value=rules),
            patch("app.api.identity.admin_libraries.manila.revoke_access_rule", mock_revoke),
        ):
            resp = await admin_client.delete("/api/admin/libraries/python311/project-access/proj-target")
        assert resp.status_code == 200
        assert resp.json()["revoked_count"] == 1
        # 레거시 rule은 revoke되지 않아야 함
        revoked_ids = [call[0][2] for call in mock_revoke.call_args_list]
        assert "rule-legacy" not in revoked_ids
        assert "rule-modern" in revoked_ids
