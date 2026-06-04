"""keystone._is_system_admin dual-mode 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_assignment():
    a = MagicMock()
    a.user = {"id": "user-1"}
    return a


_ADMIN_ROLE_ID = "admin-role-id-xyz"
_ADMIN_PROJECT_ID = "admin-project-id-abc"


@pytest.fixture(autouse=True)
def patch_resolve_admin_ids():
    with patch(
        "app.services.keystone._resolve_admin_ids",
        return_value=(_ADMIN_PROJECT_ID, _ADMIN_ROLE_ID),
    ):
        yield


class TestIsSystemAdminDualMode:
    def test_system_role_grants_admin_regardless_of_compat(self):
        """system:all role 보유자는 호환 모드 무관하게 True."""
        mock_ks = MagicMock()
        mock_ks.role_assignments.list.return_value = [_make_assignment()]

        with (
            patch("app.services.keystone._get_admin_ks_client", return_value=mock_ks),
            patch(
                "app.services.keystone.get_settings",
                return_value=MagicMock(admin_legacy_project_policy=False),
            ),
        ):
            from app.services.keystone import _is_system_admin

            assert _is_system_admin("user-1") is True

        # system="all" 검사가 먼저 호출됐는지 확인
        call_kwargs = mock_ks.role_assignments.list.call_args.kwargs
        assert call_kwargs.get("system") == "all"

    def test_admin_project_role_with_compat_on(self):
        """system role 없고 admin project+role 보유 + 호환 모드 ON → True."""
        call_count = [0]

        def _list_side_effect(**kwargs):
            call_count[0] += 1
            if kwargs.get("system") == "all":
                return []  # system role 없음
            return [_make_assignment()]  # project role 있음

        mock_ks = MagicMock()
        mock_ks.role_assignments.list.side_effect = _list_side_effect

        with (
            patch("app.services.keystone._get_admin_ks_client", return_value=mock_ks),
            patch(
                "app.services.keystone.get_settings",
                return_value=MagicMock(admin_legacy_project_policy=True),
            ),
        ):
            from app.services.keystone import _is_system_admin

            assert _is_system_admin("user-1") is True

        assert call_count[0] == 2  # system 검사 + project 검사

    def test_admin_project_role_with_compat_off(self):
        """system role 없고 admin project+role 보유 + 호환 모드 OFF → False."""

        def _list_side_effect(**kwargs):
            if kwargs.get("system") == "all":
                return []
            return [_make_assignment()]

        mock_ks = MagicMock()
        mock_ks.role_assignments.list.side_effect = _list_side_effect

        with (
            patch("app.services.keystone._get_admin_ks_client", return_value=mock_ks),
            patch(
                "app.services.keystone.get_settings",
                return_value=MagicMock(admin_legacy_project_policy=False),
            ),
        ):
            from app.services.keystone import _is_system_admin

            assert _is_system_admin("user-1") is False

    def test_no_role_returns_false(self):
        """system role도 없고 project role도 없으면 False."""
        mock_ks = MagicMock()
        mock_ks.role_assignments.list.return_value = []

        with (
            patch("app.services.keystone._get_admin_ks_client", return_value=mock_ks),
            patch(
                "app.services.keystone.get_settings",
                return_value=MagicMock(admin_legacy_project_policy=True),
            ),
        ):
            from app.services.keystone import _is_system_admin

            assert _is_system_admin("user-1") is False
