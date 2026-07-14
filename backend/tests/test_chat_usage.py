"""LibreChat 사용량 미러링 엔드포인트(/api/v1/chat/usage) 단위 테스트."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_chat_usage_unauthenticated():
    """인증 없이 호출하면 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/chat/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_chat_usage_found(client):
    """LibreChat에 매칭되는 사용자가 있으면 집계된 사용량을 반환한다."""
    fake_usage = {"total_raw_amount": -1234.0, "total_token_value": -5678.0, "transaction_count": 42}

    with patch("app.api.chat.usage.get_usage_for_username", return_value=fake_usage):
        resp = await client.get("/api/v1/chat/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["total_raw_amount"] == -1234.0
    assert data["total_token_value"] == -5678.0
    assert data["transaction_count"] == 42


@pytest.mark.asyncio
async def test_get_chat_usage_not_found(client):
    """LibreChat 미설정 또는 매칭 사용자 없음 시 found=False로 200을 반환한다(빈 상태)."""
    with patch("app.api.chat.usage.get_usage_for_username", return_value=None):
        resp = await client.get("/api/v1/chat/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["total_raw_amount"] == 0.0
    assert data["transaction_count"] == 0


@pytest.mark.asyncio
async def test_get_chat_usage_isolates_by_username(client):
    """조회 함수가 token_info의 username으로만 호출된다 (타 사용자 데이터 격리)."""
    with patch("app.api.chat.usage.get_usage_for_username", return_value=None) as mock_get:
        await client.get("/api/v1/chat/usage")

    mock_get.assert_awaited_once_with("testuser")
