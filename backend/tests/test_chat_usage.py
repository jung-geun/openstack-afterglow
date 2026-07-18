"""빌트인 AI 채팅 사용량 엔드포인트(/api/v1/chat/usage) 단위 테스트.

chat_usage_logs 원장 집계를 user_usage_summary 로 위임 — token_info 의 user_id/project_id 로만 스코프.
"""

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.chat.usage as usage_mod
from app.main import app


@pytest.mark.asyncio
async def test_get_chat_usage_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/chat/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_chat_usage_summary(client, monkeypatch):
    summary = {
        "found": True,
        "total_credited_cost": 3.5,
        "prompt_tokens": 120,
        "completion_tokens": 45,
        "request_count": 7,
    }

    async def fake_summary(user_id, project_id):
        return summary

    monkeypatch.setattr(usage_mod, "user_usage_summary", fake_summary)
    resp = await client.get("/api/v1/chat/usage")
    assert resp.status_code == 200
    assert resp.json() == summary


@pytest.mark.asyncio
async def test_get_chat_usage_scoped_to_token(client, monkeypatch):
    captured = {}

    async def fake_summary(user_id, project_id):
        captured["user_id"] = user_id
        captured["project_id"] = project_id
        return {
            "found": False,
            "total_credited_cost": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "request_count": 0,
        }

    monkeypatch.setattr(usage_mod, "user_usage_summary", fake_summary)
    resp = await client.get("/api/v1/chat/usage")
    assert resp.status_code == 200
    assert captured["user_id"] == "test-user-123"
    assert captured["project_id"] == "test-project-123"
