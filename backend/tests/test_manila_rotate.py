"""manila.rotate_cephx_access_rule 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


def _make_conn():
    return MagicMock()


def _mock_list_rules(rule_id: str, access_to: str = "test-user", access_level: str = "rw") -> list[dict]:
    return [{"id": rule_id, "access_to": access_to, "access_level": access_level}]


@patch("app.services.manila.get_client")
def test_rotate_cephx_access_rule_success(mock_get_client):
    """성공: 기존 rule revoke 후 새 rule 생성하여 새 access_key 반환."""
    from app.services.manila import rotate_cephx_access_rule

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    existing_access_id = "old-access-id"

    with (
        patch("app.services.manila.list_access_rules") as mock_list,
        patch("app.services.manila.revoke_access_rule") as mock_revoke,
        patch("app.services.manila.create_access_rule") as mock_create,
    ):
        mock_list.return_value = _mock_list_rules(existing_access_id)
        mock_create.return_value = {
            "access_id": "new-access-id",
            "access_key": "AQNEWKEYTEST==",
            "access_to": "test-user",
            "access_level": "rw",
        }

        conn = _make_conn()
        result = rotate_cephx_access_rule(conn, "share-1", existing_access_id)

    mock_revoke.assert_called_once_with(conn, "share-1", existing_access_id)
    mock_create.assert_called_once_with(conn, "share-1", "test-user", "rw", "cephx")
    assert result["access_key"] == "AQNEWKEYTEST=="
    assert result["access_id"] == "new-access-id"


@patch("app.services.manila.get_client")
def test_rotate_cephx_access_rule_not_found(mock_get_client):
    """access_id가 share에 없으면 KeyError."""
    from app.services.manila import rotate_cephx_access_rule

    mock_get_client.return_value = MagicMock()

    with patch("app.services.manila.list_access_rules") as mock_list:
        mock_list.return_value = []  # access rule 없음

        conn = _make_conn()
        with pytest.raises(KeyError, match="missing-id"):
            rotate_cephx_access_rule(conn, "share-1", "missing-id")


@patch("app.services.manila.get_client")
def test_rotate_cephx_access_rule_manila_error(mock_get_client):
    """Manila API 오류(create_access_rule) 시 예외 전파."""
    from app.services.manila import rotate_cephx_access_rule

    mock_get_client.return_value = MagicMock()

    with (
        patch("app.services.manila.list_access_rules") as mock_list,
        patch("app.services.manila.revoke_access_rule"),
        patch("app.services.manila.create_access_rule") as mock_create,
    ):
        mock_list.return_value = _mock_list_rules("old-id")
        mock_create.side_effect = RuntimeError("Manila 503")

        conn = _make_conn()
        with pytest.raises(RuntimeError, match="Manila 503"):
            rotate_cephx_access_rule(conn, "share-1", "old-id")
