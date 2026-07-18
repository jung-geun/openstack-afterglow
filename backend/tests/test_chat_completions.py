"""빌트인 AI 채팅 스트리밍 completions 라우터 테스트.

DB/네트워크 없이 credit·conversation_store·provider_store·engine 을 monkeypatch:
- 쿼터 초과 402, 대화 소유권 403, 모델 화이트리스트 위반 400
- 스트리밍 정상 경로: SSE token/done + **apply_usage 가 raw_cost>0 으로 호출**(과금 누락 회귀 방지)
"""

from decimal import Decimal

from app.services.chat import conversation_store as cs
from app.services.chat import credit, engine
from app.services.chat import provider_store as ps

_BASE = "/api/v1/chat/conversations"


async def _ok_precheck(user_id, project_id=None):
    return None


def _conv(**over) -> dict:
    base = {
        "id": "c1",
        "project_id": "test-project-123",
        "user_id": "test-user-123",
        "title": None,
        "model_name": None,
        "created_at": None,
        "updated_at": None,
    }
    base.update(over)
    return base


def _resolved(**over) -> dict:
    base = {
        "model_name": "gpt-3.5-turbo",
        "provider_name": "openai",
        "api_base": None,
        "api_key": "sk-test",
        "margin_multiplier": 1.0,
        "input_price": None,
        "output_price": None,
    }
    base.update(over)
    return base


class TestGuards:
    async def test_quota_exceeded_402(self, client, monkeypatch):
        async def fake_precheck(user_id, project_id=None):
            raise credit.QuotaExceeded("월 한도 초과")

        monkeypatch.setattr(credit, "precheck", fake_precheck)
        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "hi", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 402

    async def test_conversation_forbidden_403(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            raise cs.ConversationForbidden("접근 불가")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        resp = await client.post(f"{_BASE}/other/completions", json={"message": "hi", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 403

    async def test_unknown_model_400(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return None  # 화이트리스트에 없음

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "hi", "model": "no-such-model"})
        assert resp.status_code == 400


class TestStreamingHappyPath:
    async def test_streams_and_charges_positive_cost(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return []

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            yield {"type": "token", "text": "안녕"}
            yield {"type": "token", "text": "하세요"}
            yield {"type": "usage", "usage": None}

        captured = {}

        async def fake_apply(**kwargs):
            captured.update(kwargs)
            return Decimal("1.5")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "list_messages", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "안녕", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        body = resp.text
        assert '"token"' in body  # 델타 이벤트 전송
        assert '"done"' in body  # 종료 이벤트
        # ⚠️ 스트리밍 usage 폴백으로 raw_cost>0 이 과금되어야 한다(0원 과금 회귀 방지).
        assert captured, "apply_usage 가 호출되지 않음"
        assert captured["raw_cost"] > 0
        assert captured["provider"] == "openai"


class TestErrorPath:
    async def test_model_error_does_not_charge(self, client, monkeypatch):
        """모델 하드 실패 시 과금하지 않고 done 도 보내지 않는다(실패 요청 과금 방지)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return []

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            yield {"type": "error", "message": "모델 호출 실패"}

        called = {"apply": False}

        async def fake_apply(**kwargs):
            called["apply"] = True
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "list_messages", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "hi", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        body = resp.text
        assert '"error"' in body
        assert '"done"' not in body
        assert called["apply"] is False  # 실패한 요청에 과금하지 않음
