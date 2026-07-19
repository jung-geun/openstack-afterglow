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


class TestToolRecordPersistence:
    async def test_tool_events_persisted(self, client, monkeypatch):
        """assistant tool_calls / tool 결과 이벤트가 chat_messages 로 저장(암호화 경유)되는지."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        added: list[tuple[str, dict]] = []

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return []

        async def fake_add(conv_id, **kwargs):
            added.append((kwargs.get("role"), kwargs))
            return {"id": len(added)}

        async def fake_stream(**kwargs):
            yield {
                "type": "assistant_tool_calls",
                "content": "인스턴스를 확인할게요",
                "tool_calls": [{"id": "c1", "name": "list_instances", "args": "{}"}],
            }
            yield {"type": "tool_call", "name": "list_instances"}
            yield {"type": "tool_result", "tool_call_id": "c1", "name": "list_instances", "content": "3개"}
            yield {"type": "token", "text": "결과는 3개입니다"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "list_messages", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(
            f"{_BASE}/c1/completions", json={"message": "인스턴스 몇 개야?", "model": "gpt-3.5-turbo"}
        )
        assert resp.status_code == 200
        _ = resp.text  # 스트림 소비

        roles = [r for r, _ in added]
        # user 저장 + assistant(tool_calls) + tool 결과 + 최종 assistant
        assert roles.count("assistant") >= 2  # tool_calls 스텝 + 최종 답변
        assert "tool" in roles
        # assistant tool_calls 메시지에 tool_calls 가 실려 저장되는지
        tc_msgs = [kw for r, kw in added if r == "assistant" and kw.get("tool_calls")]
        assert tc_msgs and tc_msgs[0]["tool_calls"][0]["name"] == "list_instances"
        # tool 결과 내용 저장 + 어떤 툴 결과인지 식별 메타
        tool_msgs = [kw for r, kw in added if r == "tool"]
        assert tool_msgs and tool_msgs[0]["content"] == "3개"
        assert tool_msgs[0]["tool_calls"][0]["name"] == "list_instances"
        # 최종 답변에는 툴 스텝 선행 텍스트가 중복 포함되지 않아야 함(parts.clear)
        final_assistant = [kw for r, kw in added if r == "assistant" and not kw.get("tool_calls")]
        assert final_assistant and final_assistant[-1]["content"] == "결과는 3개입니다"

    async def test_tool_history_excluded_from_model_replay(self, client, monkeypatch):
        """저장된 role=tool 기록은 다음 턴 모델 입력에서 제외(orphaned tool → 400 회귀 방지)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        seen_messages = {}

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            # 이전 턴이 툴을 쓴 대화 이력(assistant tool_calls 스텝 + tool 결과 + 최종 답변)
            return [
                {"role": "user", "content": "인스턴스 몇 개야?"},
                {"role": "assistant", "content": "확인할게요", "tool_calls": [{"name": "list_instances"}]},
                {"role": "tool", "content": "3개", "tool_calls": [{"name": "list_instances"}]},
                {"role": "assistant", "content": "결과는 3개입니다"},
            ]

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            seen_messages["messages"] = kwargs.get("messages")
            yield {"type": "token", "text": "네"}
            yield {"type": "usage", "usage": None}

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "list_messages", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", lambda **kw: _noop())

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "고마워", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        _ = resp.text

        replayed = seen_messages["messages"]
        # role=tool 은 모델 입력에서 제외되어야 한다(orphaned tool 방지)
        assert all(m["role"] != "tool" for m in replayed)
        # 정상 user/assistant 문맥은 유지
        assert any(m["role"] == "assistant" and m["content"] == "결과는 3개입니다" for m in replayed)
        assert replayed[-1] == {"role": "user", "content": "고마워"}


async def _noop():
    return Decimal("0")


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
