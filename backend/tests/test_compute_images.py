"""compute images 엔드포인트 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import make_token_info

_MY_PROJECT = "my-project-id"
_OTHER_PROJECT = "other-project-id"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    conn._afterglow_project_id = _MY_PROJECT
    return conn


@pytest.fixture
async def user_client(mock_conn):
    from app.api.deps import get_os_conn, get_token_info

    async def override_token():
        return make_token_info(project_id=_MY_PROJECT, roles=["member"])

    async def override_conn():
        yield mock_conn

    app.dependency_overrides[get_token_info] = override_token
    app.dependency_overrides[get_os_conn] = override_conn
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_token_info, None)
    app.dependency_overrides.pop(get_os_conn, None)


# ---------------------------------------------------------------------------
# deactivate / reactivate
# ---------------------------------------------------------------------------


class TestDeactivateOwnImage:
    @pytest.mark.asyncio
    async def test_deactivate_own_image_success(self, user_client, mock_conn):
        """소유 이미지 비활성화 — 200 + SDK deactivate_image 호출."""
        fake_img = MagicMock()
        fake_img.owner = _MY_PROJECT
        mock_conn.image.get_image.return_value = fake_img

        with patch("app.api.compute.images.glance.deactivate_image") as mock_deact:
            resp = await user_client.post("/api/v1/images/img-1/deactivate")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"
        mock_deact.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_other_owner_returns_403(self, user_client, mock_conn):
        """다른 프로젝트 소유 이미지 → 403, SDK 미호출."""
        fake_img = MagicMock()
        fake_img.owner = _OTHER_PROJECT
        mock_conn.image.get_image.return_value = fake_img

        with patch("app.api.compute.images.glance.deactivate_image") as mock_deact:
            resp = await user_client.post("/api/v1/images/img-2/deactivate")

        assert resp.status_code == 403
        mock_deact.assert_not_called()

    @pytest.mark.asyncio
    async def test_reactivate_own_image_success(self, user_client, mock_conn):
        """소유 이미지 활성화 — 200 + SDK reactivate_image 호출."""
        fake_img = MagicMock()
        fake_img.owner = _MY_PROJECT
        mock_conn.image.get_image.return_value = fake_img

        with patch("app.api.compute.images.glance.reactivate_image") as mock_react:
            resp = await user_client.post("/api/v1/images/img-3/reactivate")

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        mock_react.assert_called_once()


# ---------------------------------------------------------------------------
# list_images — status 필터 검증
# ---------------------------------------------------------------------------


class TestListImagesFilter:
    def test_list_images_owner_branch_omits_status_filter(self):
        """glance.list_images의 owner 분기가 status="active"를 전달하지 않는다."""
        from app.services import glance

        captured_kwargs: list[dict] = []
        fake_conn = MagicMock()

        def fake_images(**kwargs):
            captured_kwargs.append(dict(kwargs))
            return []

        fake_conn.image.images.side_effect = fake_images
        fake_conn._afterglow_project_id = _MY_PROJECT

        glance.list_images(fake_conn, _MY_PROJECT)

        # 마지막 호출이 owner(private) 분기
        owner_call = next((kw for kw in captured_kwargs if kw.get("visibility") == "private"), None)
        assert owner_call is not None, "visibility=private 분기 호출 없음"
        assert "status" not in owner_call, "owner 분기에 status 필터가 포함되어서는 안 됩니다"
        assert owner_call.get("owner") == _MY_PROJECT
