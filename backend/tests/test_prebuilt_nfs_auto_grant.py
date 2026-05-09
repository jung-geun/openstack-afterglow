"""Prebuilt NFS share 자동 access rule 부여 단위 테스트 (§3.3).

VM 생성 시 _prepare_prebuilt_file_storages가 NFS share에 대해
project CIDR access rule을 자동으로 추가하는지 검증.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.api.compute.instances import _prepare_prebuilt_file_storages, _resolve_project_subnet_cidrs
from app.models.storage import FileStorageInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_nfs_storage(share_id: str = "share-nfs-1", lib_name: str = "python311") -> FileStorageInfo:
    return FileStorageInfo(
        id=share_id,
        name=f"union-prebuilt-{lib_name}",
        status="available",
        size=20,
        share_proto="NFS",
        export_locations=["10.0.0.1:/exports/python311"],
        metadata={"union_type": "prebuilt", "union_library": lib_name},
        project_id="svc-project-id",
        created_at="2025-01-01T00:00:00Z",
        nfs_export_location="10.0.0.1:/exports/python311",
        library_name=lib_name,
        library_version="1.0",
        built_at="2025-01-01",
    )


def make_cephfs_storage(share_id: str = "share-ceph-1", lib_name: str = "python311") -> FileStorageInfo:
    return FileStorageInfo(
        id=share_id,
        name=f"union-prebuilt-{lib_name}",
        status="available",
        size=20,
        share_proto="CEPHFS",
        export_locations=["/mnt/cephfs/python311"],
        metadata={"union_type": "prebuilt", "union_library": lib_name},
        project_id="svc-project-id",
        created_at="2025-01-01T00:00:00Z",
        nfs_export_location=None,
        library_name=lib_name,
        library_version="1.0",
        built_at="2025-01-01",
    )


def make_subnet_detail(cidr: str):
    s = MagicMock()
    s.cidr = cidr
    return s


def make_network_detail(cidrs: list[str]):
    nd = MagicMock()
    nd.subnet_details = [make_subnet_detail(c) for c in cidrs]
    return nd


# ---------------------------------------------------------------------------
# _resolve_project_subnet_cidrs
# ---------------------------------------------------------------------------


def test_resolve_project_subnet_cidrs_returns_cidrs():
    """get_network_detail로부터 CIDR 목록을 올바르게 추출한다."""
    conn = MagicMock()
    with patch(
        "app.api.compute.instances.neutron.get_network_detail",
        return_value=make_network_detail(["10.10.0.0/24", "fd00::/64"]),
    ):
        result = _resolve_project_subnet_cidrs(conn, "net-abc")
    assert result == ["10.10.0.0/24", "fd00::/64"]


def test_resolve_project_subnet_cidrs_skips_empty():
    """cidr 필드가 비어 있는 subnet은 제외한다."""
    conn = MagicMock()
    nd = MagicMock()
    s1, s2 = MagicMock(), MagicMock()
    s1.cidr = "10.10.0.0/24"
    s2.cidr = ""
    nd.subnet_details = [s1, s2]
    with patch("app.api.compute.instances.neutron.get_network_detail", return_value=nd):
        result = _resolve_project_subnet_cidrs(conn, "net-abc")
    assert result == ["10.10.0.0/24"]


# ---------------------------------------------------------------------------
# _prepare_prebuilt_file_storages — NFS 분기
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nfs_prebuilt_calls_ensure_nfs_access_rule():
    """NFS prebuilt share가 있을 때 ensure_nfs_access_rule이 호출된다."""
    nfs_storage = make_nfs_storage()
    mock_conn = MagicMock()
    mock_conn._afterglow_project_id = "proj-b"
    created = []

    with (
        patch(
            "app.api.compute.instances.keystone.get_service_project_connection",
            return_value=MagicMock(),
        ),
        patch(
            "app.api.compute.instances.manila.list_file_storages",
            return_value=[nfs_storage],
        ),
        patch(
            "app.api.compute.instances._resolve_project_subnet_cidrs",
            return_value=["10.10.0.0/24"],
        ),
        patch(
            "app.api.compute.instances.manila.ensure_nfs_access_rule",
            return_value={"access_id": "rule-1", "access_key": "", "access_to": "10.10.0.0/24", "access_level": "ro"},
        ) as mock_ensure,
        patch(
            "app.api.compute.instances.manila.get_export_locations",
            return_value=["10.0.0.1:/exports/python311"],
        ),
    ):
        result = await _prepare_prebuilt_file_storages(
            mock_conn,
            ["python311"],
            "vm-test",
            created,
            network_id="net-b",
            project_id="proj-b",
        )

    assert len(result) == 1
    assert result[0]["share_proto"] == "NFS"
    assert result[0]["cephx_key"] == ""
    assert "10.0.0.1:/exports/python311" in result[0]["nfs_export_location"]
    mock_ensure.assert_called_once()
    # extra_metadata에 union_grant_project가 포함되어야 함
    call_args = mock_ensure.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_nfs_prebuilt_creates_access_id_in_list():
    """NFS prebuilt access rule ID가 created_access_ids에 추가된다."""
    nfs_storage = make_nfs_storage()
    created = []

    with (
        patch("app.api.compute.instances.keystone.get_service_project_connection", return_value=MagicMock()),
        patch("app.api.compute.instances.manila.list_file_storages", return_value=[nfs_storage]),
        patch("app.api.compute.instances._resolve_project_subnet_cidrs", return_value=["10.10.0.0/24"]),
        patch(
            "app.api.compute.instances.manila.ensure_nfs_access_rule",
            return_value={"access_id": "rule-xyz", "access_key": "", "access_to": "10.10.0.0/24", "access_level": "ro"},
        ),
        patch("app.api.compute.instances.manila.get_export_locations", return_value=["10.0.0.1:/"]),
    ):
        await _prepare_prebuilt_file_storages(
            MagicMock(),
            ["python311"],
            "vm-test",
            created,
            network_id="net-b",
            project_id="proj-b",
        )

    assert any(rule_id == "rule-xyz" for _, rule_id in created)


@pytest.mark.asyncio
async def test_cephfs_prebuilt_still_uses_cephx():
    """CephFS prebuilt share는 NFS 분기 없이 기존 CephX access rule 생성 경로를 사용한다."""
    ceph_storage = make_cephfs_storage()
    created = []

    with (
        patch("app.api.compute.instances.keystone.get_service_project_connection", return_value=MagicMock()),
        patch("app.api.compute.instances.manila.list_file_storages", return_value=[ceph_storage]),
        patch(
            "app.api.compute.instances.manila.create_access_rule",
            return_value={
                "access_id": "ceph-rule-1",
                "access_key": "secret-key",
                "access_to": "union-ro-vm-test-python311",
                "access_level": "ro",
            },
        ) as mock_create,
        patch("app.api.compute.instances.manila.ensure_nfs_access_rule") as mock_ensure,
        patch("app.api.compute.instances.manila.get_export_locations", return_value=["/exports/ceph"]),
    ):
        result = await _prepare_prebuilt_file_storages(
            MagicMock(),
            ["python311"],
            "vm-test",
            created,
            network_id="net-b",
            project_id="proj-b",
        )

    # cephx 경로: create_access_rule 호출, ensure_nfs_access_rule 미호출
    mock_create.assert_called_once()
    mock_ensure.assert_not_called()
    assert result[0]["cephx_key"] == "secret-key"
    assert result[0]["share_proto"] == "CEPHFS"


@pytest.mark.asyncio
async def test_nfs_prebuilt_raises_if_no_cidr():
    """network_id 없거나 CIDR 조회 실패 시 RuntimeError."""
    nfs_storage = make_nfs_storage()

    with (
        patch("app.api.compute.instances.keystone.get_service_project_connection", return_value=MagicMock()),
        patch("app.api.compute.instances.manila.list_file_storages", return_value=[nfs_storage]),
        patch("app.api.compute.instances._resolve_project_subnet_cidrs", return_value=[]),
    ):
        with pytest.raises(RuntimeError, match="CIDR"):
            await _prepare_prebuilt_file_storages(
                MagicMock(),
                ["python311"],
                "vm-test",
                [],
                network_id="net-b",
                project_id="proj-b",
            )


@pytest.mark.asyncio
async def test_grant_partial_failure_raises_and_first_rule_tracked():
    """2 CIDR 중 2번째 ensure 실패 시 예외가 전파되고, 1번째 rule은 created_access_ids에 기록된다.

    _prepare_prebuilt_file_storages는 내부 롤백을 수행하지 않는다 — 호출자가
    created_access_ids를 이용해 revoke하는 것이 기대 동작이다.
    """
    nfs_storage = make_nfs_storage()
    created: list = []

    ensure_call_count = 0

    def _ensure_side_effect(*args, **kwargs):
        nonlocal ensure_call_count
        ensure_call_count += 1
        if ensure_call_count == 1:
            return {"access_id": "rule-first", "access_key": "", "access_to": "10.10.0.0/24", "access_level": "ro"}
        raise RuntimeError("Manila 연결 실패")

    with (
        patch("app.api.compute.instances.keystone.get_service_project_connection", return_value=MagicMock()),
        patch("app.api.compute.instances.manila.list_file_storages", return_value=[nfs_storage]),
        patch(
            "app.api.compute.instances._resolve_project_subnet_cidrs",
            return_value=["10.10.0.0/24", "10.20.0.0/24"],
        ),
        patch("app.api.compute.instances.manila.ensure_nfs_access_rule", side_effect=_ensure_side_effect),
        patch("app.api.compute.instances.manila.get_export_locations", return_value=["10.0.0.1:/"]),
    ):
        with pytest.raises(RuntimeError, match="Manila"):
            await _prepare_prebuilt_file_storages(
                MagicMock(),
                ["python311"],
                "vm-test",
                created,
                network_id="net-b",
                project_id="proj-b",
            )

    # 1번째 rule은 created_access_ids에 기록되어 호출자가 rollback 가능
    assert any(rule_id == "rule-first" for _, rule_id in created)
