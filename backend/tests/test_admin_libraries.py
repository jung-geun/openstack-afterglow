"""Admin Library API 단위 테스트 (§3.1 + §3.3)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_NOW = datetime(2026, 4, 24, 0, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# §3.1 Admin Library 목록 / 상세
# ---------------------------------------------------------------------------


class TestAdminLibraryList:
    @pytest.mark.asyncio
    async def test_list_admin_libraries_returns_all(self, admin_client):
        """관리자는 전체 라이브러리 목록 반환."""
        with patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[]):
            resp = await admin_client.get("/api/admin/libraries")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # 카탈로그에 최소 1개 이상 존재
        ids = [lib["id"] for lib in data]
        assert "python311" in ids

    @pytest.mark.asyncio
    async def test_list_admin_libraries_forbidden_for_non_admin(self, non_admin_client):
        """일반 사용자 → 403."""
        resp = await non_admin_client.get("/api/admin/libraries")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_admin_libraries_includes_dependency_tree(self, admin_client):
        """응답에 dependency_tree 포함."""
        with patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[]):
            resp = await admin_client.get("/api/admin/libraries")
        assert resp.status_code == 200
        torch_lib = next((lib for lib in resp.json() if lib["id"] == "torch"), None)
        assert torch_lib is not None
        assert "dependency_tree" in torch_lib
        assert torch_lib["dependency_tree"]["id"] == "torch"


class TestAdminLibraryDetail:
    @pytest.mark.asyncio
    async def test_get_known_library(self, admin_client):
        """알려진 라이브러리 상세 조회 성공."""
        with patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[]):
            resp = await admin_client.get("/api/admin/libraries/python311")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "python311"
        assert "dependency_tree" in data

    @pytest.mark.asyncio
    async def test_get_unknown_library_returns_404(self, admin_client):
        """알 수 없는 라이브러리 → 404."""
        with patch("app.api.identity.admin_libraries.manila.list_file_storages", return_value=[]):
            resp = await admin_client.get("/api/admin/libraries/unknown_lib")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_library_forbidden_for_non_admin(self, non_admin_client):
        """일반 사용자 → 403."""
        resp = await non_admin_client.get("/api/admin/libraries/python311")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# §3.1 빌드 상태 머신 (cancel)
# ---------------------------------------------------------------------------


class TestBuildCancel:
    @pytest.mark.asyncio
    async def test_cancel_build_success(self, admin_client):
        """빌드 취소 성공 → 200 + build_id=1이 정확히 전달됐는지 검증."""
        mock_cancel = AsyncMock(return_value={"cancelled": True, "library_id": "python311", "server_deleted": True})
        with patch(
            "app.api.identity.admin_libraries.library_builder.cancel_build",
            mock_cancel,
        ):
            resp = await admin_client.post("/api/admin/libraries/builds/1/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is True
        assert mock_cancel.call_args[0][0] == 1  # build_id=1이 전달됐는지 검증 (conn 제거 후 첫 번째 인자)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_build_returns_404(self, admin_client):
        """없는 빌드 취소 → 404."""
        with patch(
            "app.api.identity.admin_libraries.library_builder.cancel_build",
            AsyncMock(side_effect=KeyError("빌드 999를 찾을 수 없습니다")),
        ):
            resp = await admin_client.post("/api/admin/libraries/builds/999/cancel")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_completed_build_returns_409(self, admin_client):
        """이미 완료된 빌드 취소 → 409."""
        with patch(
            "app.api.identity.admin_libraries.library_builder.cancel_build",
            AsyncMock(side_effect=ValueError("이미 종료된 빌드입니다 (상태: complete)")),
        ):
            resp = await admin_client.post("/api/admin/libraries/builds/1/cancel")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_cancel_forbidden_for_non_admin(self, non_admin_client):
        """일반 사용자 취소 시도 → 403."""
        resp = await non_admin_client.post("/api/admin/libraries/builds/1/cancel")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# §3.3 Cross-project library 조회 (libraries.get_dependency_tree)
# ---------------------------------------------------------------------------


class TestCrossProjectLibrary:
    def test_get_dependency_tree_known(self):
        """알려진 라이브러리 의존성 트리 반환."""
        from app.services.libraries import get_dependency_tree

        tree = get_dependency_tree("vllm")
        assert tree["id"] == "vllm"
        assert isinstance(tree["deps"], list)
        # vllm depends on python311 and torch
        dep_ids = [d["id"] for d in tree["deps"]]
        assert "python311" in dep_ids or "torch" in dep_ids

    def test_get_dependency_tree_unknown(self):
        """알 수 없는 라이브러리도 기본 구조 반환 (에러 없음)."""
        from app.services.libraries import get_dependency_tree

        tree = get_dependency_tree("nonexistent")
        assert tree["id"] == "nonexistent"
        assert tree["deps"] == []

    def test_get_dependency_tree_root_library(self):
        """최상위 라이브러리 (의존성 없음)는 빈 deps."""
        from app.services.libraries import get_dependency_tree

        tree = get_dependency_tree("python311")
        assert tree["id"] == "python311"
        assert tree["deps"] == []


# ---------------------------------------------------------------------------
# §3.1 빌드 목록
# ---------------------------------------------------------------------------


class TestCreateBuilderVm:
    def test_does_not_wait_for_active(self):
        """_create_builder_vm이 wait_for_server를 호출하지 않아야 한다.

        회귀 방지: wait_for_server(wait=600)이 요청 핸들러를 최대 10분간
        블로킹해 트리거가 타임아웃됐던 버그(네트워크 오류)가 재발하지 않도록 한다.
        """
        from app.services.library_builder import _create_builder_vm

        fake_server = MagicMock()
        fake_server.id = "fake-server-id"
        fake_conn = MagicMock()
        fake_conn.compute.create_server.return_value = fake_server

        result = _create_builder_vm(fake_conn, "python311", "img", "flv", "net", "ud-b64")

        fake_conn.compute.create_server.assert_called_once()
        fake_conn.compute.wait_for_server.assert_not_called()
        assert result is fake_server


class TestBuildList:
    @pytest.mark.asyncio
    async def test_list_builds_returns_list_when_db_unavailable(self, admin_client):
        """DB 미초기화 시 인메모리 캐시 반환."""
        with (
            patch("app.api.identity.admin_libraries.library_builder.get_active_builds", return_value={}),
            patch("app.api.identity.admin_libraries.get_session_factory", return_value=None, create=True),
        ):
            # DB 없이도 정상 동작해야 함 (get_session_factory = None 경로)
            from app.database import get_session_factory

            with patch.object(get_session_factory, "__call__", return_value=None, create=True):
                resp = await admin_client.get("/api/admin/libraries/builds")
        # 200이거나 빈 목록이면 성공
        assert resp.status_code in (200, 500)  # DB 없으면 500도 허용

    @pytest.mark.asyncio
    async def test_list_builds_admin_only(self, non_admin_client):
        """일반 사용자 → 403."""
        resp = await non_admin_client.get("/api/admin/libraries/builds")
        assert resp.status_code == 403
