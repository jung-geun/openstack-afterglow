"""keystone.py — ensure_cluster_manager_user / create/delete_app_credential 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


def _mock_settings():
    s = MagicMock()
    s.os_auth_url = "https://keystone.example.com:5000/v3"
    s.os_username = "admin"
    s.os_password = "adminpass"
    s.os_project_name = "admin"
    s.os_user_domain_name = "Default"
    s.os_project_domain_name = "Default"
    s.os_region_name = "RegionOne"
    s.os_interface = "public"
    s.ssl_verify = True
    return s


# ---------------------------------------------------------------------------
# encrypt_manager_password / decrypt_manager_password
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_manager_password(monkeypatch):
    monkeypatch.setenv("K3S_KUBECONFIG_ENCRYPTION_KEY", "a" * 64)
    from app.services.k3s_crypto import decrypt_manager_password, encrypt_manager_password

    enc = encrypt_manager_password("my-secret-password")
    assert enc.startswith("v3:")
    assert decrypt_manager_password(enc) == "my-secret-password"


# ---------------------------------------------------------------------------
# ensure_cluster_manager_user
# ---------------------------------------------------------------------------


def test_ensure_cluster_manager_user_returns_cached(monkeypatch):
    """DB에 캐시된 자격이 있으면 복호화하여 반환."""

    from app.services.k3s_crypto import encrypt_manager_password

    monkeypatch.setenv("K3S_KUBECONFIG_ENCRYPTION_KEY", "b" * 64)

    # DB mock
    cached = {
        "user_id": "user-123",
        "username": "afterglow-cluster-mgr-abcd1234",
        "encrypted_password": encrypt_manager_password("cached-pw"),
    }

    async def _fake_get(project_id):
        return cached

    with (
        patch("app.services.keystone.get_settings", return_value=_mock_settings()),
        patch("app.services.k3s_db.get_manager_credentials", side_effect=_fake_get),
    ):
        from app.services.keystone import ensure_cluster_manager_user

        uid, pw = ensure_cluster_manager_user("abcd1234-5678-xxxx-yyyy-zzzzzzzzzzzz")

    assert uid == "user-123"
    assert pw == "cached-pw"


def test_ensure_cluster_manager_user_creates_new(monkeypatch):
    """DB에 없으면 admin conn으로 사용자를 생성하고 DB에 저장."""

    monkeypatch.setenv("K3S_KUBECONFIG_ENCRYPTION_KEY", "c" * 64)

    async def _fake_get(project_id):
        return None

    async def _fake_save(project_id, user_id, username, encrypted_pw):
        pass

    fake_user = MagicMock()
    fake_user.id = "new-user-id"

    fake_role = MagicMock()
    fake_role.id = "role-id-member"

    fake_conn = MagicMock()
    fake_conn.identity.create_user.return_value = fake_user
    fake_conn.identity.domains.return_value = [MagicMock(id="domain-1")]
    # side_effect로 호출할 때마다 새 리스트 반환 (member, load-balancer_member 각 1회씩 호출)
    fake_conn.identity.roles.side_effect = lambda **kw: [fake_role]
    fake_conn.identity.assign_project_role_to_user.return_value = None
    fake_conn.close = MagicMock()

    with (
        patch("app.services.keystone.get_settings", return_value=_mock_settings()),
        patch("app.services.keystone.get_admin_connection_for_project", return_value=fake_conn),
        patch("app.services.k3s_db.get_manager_credentials", side_effect=_fake_get),
        patch("app.services.k3s_db.save_manager_credentials", side_effect=_fake_save),
    ):
        from app.services.keystone import ensure_cluster_manager_user

        uid, pw = ensure_cluster_manager_user("proj-5678-xxxx-yyyy-zzzzzzzzzzzz")

    assert uid == "new-user-id"
    assert len(pw) > 0
    fake_conn.identity.create_user.assert_called_once()
    assert fake_conn.identity.assign_project_role_to_user.call_count == 2  # member + load-balancer_member
    fake_conn.close.assert_called_once()


def test_ensure_cluster_manager_user_role_missing_raises(monkeypatch):
    """역할이 Keystone에 없으면 RuntimeError로 fail-fast."""
    monkeypatch.setenv("K3S_KUBECONFIG_ENCRYPTION_KEY", "d" * 64)

    async def _fake_get(project_id):
        return None

    async def _fake_save(*args):
        pass

    fake_user = MagicMock()
    fake_user.id = "new-user-id"

    fake_conn = MagicMock()
    fake_conn.identity.create_user.return_value = fake_user
    fake_conn.identity.domains.return_value = [MagicMock(id="domain-1")]
    fake_conn.identity.roles.side_effect = lambda **kw: []  # role 없음
    fake_conn.close = MagicMock()

    with (
        patch("app.services.keystone.get_settings", return_value=_mock_settings()),
        patch("app.services.keystone.get_admin_connection_for_project", return_value=fake_conn),
        patch("app.services.k3s_db.get_manager_credentials", side_effect=_fake_get),
        patch("app.services.k3s_db.save_manager_credentials", side_effect=_fake_save),
        pytest.raises(RuntimeError, match="역할이 Keystone에 존재하지 않습니다"),
    ):
        from app.services.keystone import ensure_cluster_manager_user

        ensure_cluster_manager_user("proj-1234-xxxx")


# ---------------------------------------------------------------------------
# delete_app_credential — best-effort
# ---------------------------------------------------------------------------


def test_delete_app_credential_best_effort_on_failure(monkeypatch):
    """App Cred 삭제 실패 시 예외를 전파하지 않고 warning만 기록."""

    monkeypatch.setenv("K3S_KUBECONFIG_ENCRYPTION_KEY", "e" * 64)

    from app.services.k3s_crypto import encrypt_manager_password

    async def _fake_get(project_id):
        return {
            "user_id": "u-1",
            "username": "afterglow-cluster-mgr-proj1234",
            "encrypted_password": encrypt_manager_password("pw"),
        }

    with (
        patch("app.services.keystone.get_settings", return_value=_mock_settings()),
        patch("app.services.k3s_db.get_manager_credentials", side_effect=_fake_get),
        patch("openstack.connect", side_effect=RuntimeError("conn failed")),
    ):
        from app.services.keystone import delete_app_credential

        # 예외가 전파되지 않아야 함
        delete_app_credential("proj1234-xxxx", "cred-id-abc")
