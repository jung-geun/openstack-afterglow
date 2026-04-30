"""Manila NFS 보안 옵션 단위 테스트.

A5: root_squash 강제 + sec_flavor 옵션 (Manila API v2.65 metadata 필드)
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# _build_nfs_access_metadata
# ---------------------------------------------------------------------------


def test_build_nfs_metadata_defaults():
    """기본값: root_squash=True, sec_flavor="sys"."""
    from app.services.manila import _build_nfs_access_metadata

    meta = _build_nfs_access_metadata()
    assert meta == {"root_squash": "True", "auth_flavor_list": ["sys"]}


def test_build_nfs_metadata_root_squash_false():
    """root_squash=False 시 root_squash 키 제외."""
    from app.services.manila import _build_nfs_access_metadata

    meta = _build_nfs_access_metadata(root_squash=False, sec_flavor="sys")
    assert "root_squash" not in meta
    assert meta["auth_flavor_list"] == ["sys"]


def test_build_nfs_metadata_krb5():
    """sec_flavor="krb5" 시 auth_flavor_list에 krb5 반영."""
    from app.services.manila import _build_nfs_access_metadata

    meta = _build_nfs_access_metadata(root_squash=True, sec_flavor="krb5")
    assert meta["root_squash"] == "True"
    assert meta["auth_flavor_list"] == ["krb5"]


def test_build_nfs_metadata_empty_flavor():
    """sec_flavor="" 시 auth_flavor_list 키 제외."""
    from app.services.manila import _build_nfs_access_metadata

    meta = _build_nfs_access_metadata(root_squash=True, sec_flavor="")
    assert "auth_flavor_list" not in meta


# ---------------------------------------------------------------------------
# create_access_rule — metadata 파라미터
# ---------------------------------------------------------------------------


def _make_manila_client_mock(access_id: str = "rule-id", access_level: str = "rw"):
    client = MagicMock()
    client.post.return_value = {
        "access": {
            "id": access_id,
            "access_type": "ip",
            "access_to": "10.0.0.1",
            "access_level": access_level,
            "state": "new",
        }
    }
    return client


@patch("app.services.manila.get_client")
def test_create_access_rule_ip_with_metadata(mock_get_client):
    """IP access rule 생성 시 metadata가 allow_access에 포함되어야 한다."""
    from app.services.manila import create_access_rule

    client = _make_manila_client_mock()
    mock_get_client.return_value = client

    conn = MagicMock()
    meta = {"root_squash": "True", "auth_flavor_list": ["sys"]}
    create_access_rule(conn, "share-1", "10.0.0.1", "rw", "ip", metadata=meta)

    posted_body = client.post.call_args[0][1]
    assert posted_body["allow_access"]["metadata"] == meta


@patch("app.services.manila.get_client")
def test_create_access_rule_ip_no_metadata_when_none(mock_get_client):
    """metadata=None 시 allow_access에 metadata 키 없음."""
    from app.services.manila import create_access_rule

    client = _make_manila_client_mock()
    mock_get_client.return_value = client

    conn = MagicMock()
    create_access_rule(conn, "share-1", "10.0.0.1", "rw", "ip", metadata=None)

    posted_body = client.post.call_args[0][1]
    assert "metadata" not in posted_body["allow_access"]


@patch("app.services.manila.get_client")
def test_create_access_rule_cephx_ignores_metadata(mock_get_client):
    """CephX access rule 생성 시 metadata가 전달돼도 allow_access에 포함하지 않는다."""
    from app.services.manila import create_access_rule

    client = MagicMock()
    client.post.return_value = {
        "access": {
            "id": "cephx-rule-id",
            "access_type": "cephx",
            "access_to": "client.test",
            "access_level": "rw",
            "state": "new",
        }
    }
    # _get_access_key 폴링 우회
    client.get.return_value = {"access_rules": [{"id": "cephx-rule-id", "access_key": "AQTEST=="}]}
    mock_get_client.return_value = client

    conn = MagicMock()
    meta = {"root_squash": "True"}
    create_access_rule(conn, "share-1", "client.test", "rw", "cephx", metadata=meta)

    posted_body = client.post.call_args[0][1]
    assert "metadata" not in posted_body["allow_access"]


# ---------------------------------------------------------------------------
# ensure_nfs_access_rule — 보안 메타데이터 포함 생성
# ---------------------------------------------------------------------------


@patch("app.services.manila.list_access_rules")
@patch("app.services.manila.create_access_rule")
def test_ensure_nfs_access_rule_creates_with_security_metadata(mock_create, mock_list):
    """기존 rule 없을 때 root_squash + sec_flavor 메타데이터와 함께 새 rule 생성."""
    from app.services.manila import ensure_nfs_access_rule

    mock_list.return_value = []
    mock_create.return_value = {
        "access_id": "new-rule",
        "access_key": "",
        "access_to": "10.0.0.5",
        "access_level": "rw",
    }

    conn = MagicMock()
    result = ensure_nfs_access_rule(
        conn,
        "share-1",
        "10.0.0.5",
        "rw",
        root_squash=True,
        sec_flavor="sys",
    )

    assert result["access_id"] == "new-rule"
    # create_access_rule이 metadata와 함께 호출됐는지 검증
    _, kwargs = mock_create.call_args
    passed_meta = (
        kwargs.get("metadata") or mock_create.call_args[0][5]
        if len(mock_create.call_args[0]) > 5
        else kwargs.get("metadata")
    )
    # positional or keyword — 어느 방식으로든 metadata가 전달됐어야 한다
    call_kwargs = mock_create.call_args.kwargs
    call_args = mock_create.call_args.args
    if "metadata" in call_kwargs:
        passed_meta = call_kwargs["metadata"]
    else:
        # positional: conn, file_storage_id, access_to, access_level, access_type, metadata
        passed_meta = call_args[5] if len(call_args) > 5 else None
    assert passed_meta is not None
    assert passed_meta.get("root_squash") == "True"
    assert passed_meta.get("auth_flavor_list") == ["sys"]


@patch("app.services.manila.list_access_rules")
@patch("app.services.manila.create_access_rule")
def test_ensure_nfs_access_rule_returns_existing_without_create(mock_create, mock_list):
    """기존 active rule이 있으면 create_access_rule을 호출하지 않아야 한다."""
    from app.services.manila import ensure_nfs_access_rule

    mock_list.return_value = [
        {
            "id": "existing-rule",
            "access_type": "ip",
            "access_to": "10.0.0.5",
            "access_level": "rw",
            "state": "active",
        }
    ]

    conn = MagicMock()
    result = ensure_nfs_access_rule(conn, "share-1", "10.0.0.5", "rw")

    mock_create.assert_not_called()
    assert result["access_id"] == "existing-rule"


@patch("app.services.manila.list_access_rules")
@patch("app.services.manila.create_access_rule")
def test_ensure_nfs_access_rule_krb5(mock_create, mock_list):
    """sec_flavor=krb5 옵션이 메타데이터에 반영된다."""
    from app.services.manila import ensure_nfs_access_rule

    mock_list.return_value = []
    mock_create.return_value = {
        "access_id": "krb5-rule",
        "access_key": "",
        "access_to": "192.168.1.10",
        "access_level": "rw",
    }

    conn = MagicMock()
    ensure_nfs_access_rule(
        conn,
        "share-2",
        "192.168.1.10",
        "rw",
        root_squash=True,
        sec_flavor="krb5",
    )

    call_kwargs = mock_create.call_args.kwargs
    call_args = mock_create.call_args.args
    if "metadata" in call_kwargs:
        passed_meta = call_kwargs["metadata"]
    else:
        passed_meta = call_args[5] if len(call_args) > 5 else None
    assert passed_meta is not None
    assert passed_meta.get("auth_flavor_list") == ["krb5"]


@patch("app.services.manila.list_access_rules")
@patch("app.services.manila.create_access_rule")
def test_ensure_nfs_access_rule_root_squash_disabled(mock_create, mock_list):
    """root_squash=False 시 메타데이터에 root_squash 키 없음."""
    from app.services.manila import ensure_nfs_access_rule

    mock_list.return_value = []
    mock_create.return_value = {
        "access_id": "nosquash-rule",
        "access_key": "",
        "access_to": "10.0.0.1",
        "access_level": "ro",
    }

    conn = MagicMock()
    ensure_nfs_access_rule(
        conn,
        "share-3",
        "10.0.0.1",
        "ro",
        root_squash=False,
        sec_flavor="sys",
    )

    call_kwargs = mock_create.call_args.kwargs
    call_args = mock_create.call_args.args
    if "metadata" in call_kwargs:
        passed_meta = call_kwargs["metadata"]
    else:
        passed_meta = call_args[5] if len(call_args) > 5 else None
    assert passed_meta is not None
    assert "root_squash" not in passed_meta


# ---------------------------------------------------------------------------
# Settings — 새 config 필드 기본값
# ---------------------------------------------------------------------------


def test_settings_manila_nfs_defaults():
    """Manila NFS 보안 설정 기본값 확인."""
    from app.config import Settings

    s = Settings()
    assert s.manila_nfs_root_squash is True
    assert s.manila_nfs_sec_flavor == "sys"


def test_settings_manila_nfs_env_override(monkeypatch):
    """환경변수로 NFS 보안 옵션을 오버라이드할 수 있다."""
    from app.config import Settings

    monkeypatch.setenv("MANILA_NFS_ROOT_SQUASH", "false")
    monkeypatch.setenv("MANILA_NFS_SEC_FLAVOR", "krb5")
    s = Settings()
    assert s.manila_nfs_root_squash is False
    assert s.manila_nfs_sec_flavor == "krb5"
