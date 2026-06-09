"""C4: X-Auth-Token 제거 — X-Auth-Token 사용 시 401 반환 확인.

이 테스트는 dependency_overrides를 사용하는 client 픽스처를 사용하지 않는다.
실제 get_token_info를 거쳐 X-Auth-Token이 거부되는지 직접 검증한다.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_x_auth_token_only_returns_401():
    """X-Auth-Token만 보내고 Bearer가 없으면 401을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/k3s/clusters",
            headers={"X-Auth-Token": "some-keystone-token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_header_returns_401():
    """인증 헤더 없이 보호된 엔드포인트에 접근하면 401을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/k3s/clusters")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_x_auth_token_with_x_project_id_returns_401():
    """X-Auth-Token + X-Project-Id 조합도 401을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/instances",
            headers={
                "X-Auth-Token": "some-keystone-token",
                "X-Project-Id": "some-project-id",
            },
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_download_without_dl_token_returns_403():
    """다운로드 토큰 없이 download 엔드포인트를 호출하면 403을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/object-storage/my-container/objects/my-file.txt/download")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_download_with_x_auth_token_only_returns_403():
    """X-Auth-Token으로 download 엔드포인트에 접근하면 403을 반환해야 한다 (dl_token 없음)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/object-storage/my-container/objects/my-file.txt/download",
            headers={"X-Auth-Token": "some-keystone-token"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_error_message_mentions_bearer():
    """401 응답의 detail이 Bearer 토큰을 요청하는 메시지여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/instances")
    assert resp.status_code == 401
    data = resp.json()
    assert "Bearer" in data.get("detail", "")
