"""manila.list_file_storages caller_project_id 격리 필터 단위 테스트."""

from unittest.mock import MagicMock, patch

from app.models.storage import FileStorageInfo


def _make_fs(fs_id: str, owner: str, is_public: bool = False) -> FileStorageInfo:
    return FileStorageInfo(
        id=fs_id,
        name=fs_id,
        status="available",
        size=10,
        share_proto="CEPHFS",
        metadata={"union_project_id": owner} if owner else {},
        is_public=is_public,
    )


def _mock_client_response(shares: list[dict]):
    client = MagicMock()
    client.get.return_value = {"shares": shares}
    return client


def _raw(fs: FileStorageInfo) -> dict:
    """FileStorageInfo → Manila raw share dict 형태 변환."""
    return {
        "id": fs.id,
        "name": fs.name,
        "status": fs.status,
        "size": fs.size,
        "share_proto": fs.share_proto,
        "export_locations": [],
        "metadata": fs.metadata,
        "project_id": None,
        "created_at": None,
        "is_public": fs.is_public,
    }


@patch("app.services.manila.get_client")
def test_caller_project_id_hides_other_project_share(mock_get_client):
    """caller_project_id 지정 시 다른 프로젝트 소유의 private share는 제외."""
    from app.services.manila import list_file_storages

    own = _make_fs("mine", owner="proj-A")
    other = _make_fs("other", owner="proj-B")
    mock_get_client.return_value = _mock_client_response([_raw(own), _raw(other)])

    conn = MagicMock()
    result = list_file_storages(conn, caller_project_id="proj-A")
    ids = [s.id for s in result]
    assert "mine" in ids
    assert "other" not in ids


@patch("app.services.manila.get_client")
def test_caller_project_id_exposes_public_share(mock_get_client):
    """is_public=True share는 다른 프로젝트가 caller여도 노출."""
    from app.services.manila import list_file_storages

    public = _make_fs("public-share", owner="proj-B", is_public=True)
    mock_get_client.return_value = _mock_client_response([_raw(public)])

    conn = MagicMock()
    result = list_file_storages(conn, caller_project_id="proj-A")
    assert any(s.id == "public-share" for s in result)
