"""빌트인 AI 채팅 스트리밍 completions 라우터 테스트.

DB/네트워크 없이 credit·conversation_store·provider_store·engine 을 monkeypatch:
- 쿼터 초과 402, 대화 소유권 403, 모델 화이트리스트 위반 400
- 스트리밍 정상 경로: SSE token/done + immutable UsageCost 원장 호출
"""

from decimal import Decimal

from app.services.chat import agent_store as ags
from app.services.chat import conversation_store as cs
from app.services.chat import credit, engine
from app.services.chat import memory_store as ms
from app.services.chat import provider_store as ps
from app.services.chat import workspace_store as ws

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
        "margin_multiplier": Decimal("1.0"),
        "input_price_per_token": Decimal("0.000002"),
        "output_price_per_token": Decimal("0.000008"),
        "price_source": "manual",
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
            return {"messages": [], "active_leaf_id": None}

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
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "안녕", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        body = resp.text
        assert '"token"' in body  # 델타 이벤트 전송
        assert '"done"' in body  # 종료 이벤트
        assert captured, "apply_usage 가 호출되지 않음"
        assert captured["usage_cost"].raw_cost > 0
        assert captured["provider"] == "openai"
        assert captured["event_id"]

    async def test_request_reasoning_effort_overrides_global(self, client, monkeypatch):
        """요청 본문의 reasoning_effort 가 engine.stream 으로 전달된다(전역 기본 대신)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        captured: dict = {}

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            yield {"type": "token", "text": "x"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(
            f"{_BASE}/c1/completions",
            json={"message": "hi", "model": "gpt-3.5-turbo", "reasoning_effort": "high"},
        )
        assert resp.status_code == 200
        _ = resp.text
        assert captured.get("reasoning_effort") == "high"

    async def test_image_attachment_multimodal_for_vision_model(self, client, monkeypatch):
        """vision 모델 + 이미지 첨부 → 마지막 user 턴이 멀티모달 content 배열 + user 메시지에 attachments 저장."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        captured: dict = {}
        saved: list[dict] = []

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved(capabilities={"vision": True})

        async def fake_list(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            saved.append(kwargs)
            return {"id": len(saved)}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            yield {"type": "token", "text": "보입니다"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        def fake_resolve_url(token, uid, pid, key, mime):
            return "https://presigned/x.png"

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)
        from app.services.chat import attachments as att

        monkeypatch.setattr(att, "resolve_image_url", fake_resolve_url)

        resp = await client.post(
            f"{_BASE}/c1/completions",
            json={
                "message": "이게 뭐야?",
                "model": "gpt-4o",
                "attachments": [{"key": "u/abc/x.png", "mime": "image/png", "name": "x.png"}],
            },
        )
        assert resp.status_code == 200
        _ = resp.text
        # engine.stream 에 전달된 마지막 user 메시지 = 멀티모달 배열(text + image_url)
        last = captured["messages"][-1]
        assert isinstance(last["content"], list)
        assert any(
            p.get("type") == "image_url" and p["image_url"]["url"] == "https://presigned/x.png"
            for p in last["content"]
        )
        # user 메시지 저장에 attachments 참조가 실림
        user_saved = [kw for kw in saved if kw.get("role") == "user"]
        assert user_saved and user_saved[0]["attachments"][0]["key"] == "u/abc/x.png"

    async def test_attachment_ignored_for_non_vision_model(self, client, monkeypatch):
        """vision 미지원 모델은 첨부를 멀티모달로 넣지 않는다(content 는 문자열 유지)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        captured: dict = {}

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved(capabilities={"vision": False})

        async def fake_list(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            yield {"type": "token", "text": "x"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(
            f"{_BASE}/c1/completions",
            json={
                "message": "hi",
                "model": "gpt-3.5-turbo",
                "attachments": [{"key": "u/abc/x.png", "mime": "image/png", "name": "x.png"}],
            },
        )
        assert resp.status_code == 200
        _ = resp.text
        assert isinstance(captured["messages"][-1]["content"], str)

    async def test_reasoning_forwarded_and_persisted(self, client, monkeypatch):
        """reasoning 이벤트는 SSE 로 중계되고 최종 assistant 메시지에 저장된다(재로딩 시 유지)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        added: list[tuple[str, dict]] = []

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            added.append((kwargs.get("role"), kwargs))
            return {"id": len(added)}

        async def fake_stream(**kwargs):
            yield {"type": "reasoning", "text": "단계적으로 생각"}
            yield {"type": "token", "text": "정답"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "17*23?", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        body = resp.text
        assert '"reasoning"' in body and "단계적으로 생각" in body  # SSE 중계
        # 최종 assistant 저장에 reasoning 이 실린다(본문 content 와는 별개 필드)
        final_assistant = [kw for r, kw in added if r == "assistant"]
        assert final_assistant and final_assistant[-1]["reasoning"] == "단계적으로 생각"
        assert final_assistant[-1]["content"] == "정답"  # 추론이 본문에 섞이지 않음

    async def test_citations_persisted_and_forwarded(self, client, monkeypatch):
        """citations 이벤트 → 최종 assistant 메시지에 저장 + SSE 중계."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)
        added: list[tuple[str, dict]] = []

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_resolve(model_name):
            return _resolved()

        async def fake_list(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            added.append((kwargs.get("role"), kwargs))
            return {"id": len(added)}

        async def fake_stream(**kwargs):
            yield {"type": "token", "text": "서울과 부산입니다"}
            yield {"type": "citations", "items": [{"url": "https://a.com", "title": "A", "snippet": "s"}]}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "큰 도시?", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        body = resp.text
        assert '"citations"' in body and "https://a.com" in body  # SSE 중계
        # 최종 assistant 저장에 citations 실림
        final_assistant = [kw for r, kw in added if r == "assistant"]
        assert final_assistant and final_assistant[-1]["citations"][0]["url"] == "https://a.com"


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
            return {"messages": [], "active_leaf_id": None}

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
        monkeypatch.setattr(cs, "get_active_path", fake_list)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(
            f"{_BASE}/c1/completions", json={"message": "인스턴스 몇 개야?", "model": "gpt-3.5-turbo"}
        )
        assert resp.status_code == 200
        body = resp.text  # 스트림 소비

        # 시각화용 SSE 중계 — 툴 호출(인자)/결과가 프론트로 전달되는지
        assert '"tool_calls"' in body and '"list_instances"' in body
        assert '"tool_result"' in body and '"3개"' in body

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
            # 이전 턴이 툴을 쓴 활성 경로(assistant tool_calls 스텝 + tool 결과 + 최종 답변)
            return {
                "messages": [
                    {"role": "user", "content": "인스턴스 몇 개야?"},
                    {"role": "assistant", "content": "확인할게요", "tool_calls": [{"name": "list_instances"}]},
                    {"role": "tool", "content": "3개", "tool_calls": [{"name": "list_instances"}]},
                    {"role": "assistant", "content": "결과는 3개입니다"},
                ],
                "active_leaf_id": 99,
            }

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            seen_messages["messages"] = kwargs.get("messages")
            yield {"type": "token", "text": "네"}
            yield {"type": "usage", "usage": None}

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
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
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_stream(**kwargs):
            yield {"type": "error", "message": "모델 호출 실패"}

        called = {"apply": False}

        async def fake_apply(**kwargs):
            called["apply"] = True
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_list)
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


class TestRegenerate:
    async def test_regenerate_creates_sibling_under_turn_user(self, client, monkeypatch):
        """재생성: 턴-시작 user 아래 새 assistant 형제(다른 모델), active_leaf 이동."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv(model_name="gpt-3.5-turbo")

        async def fake_turn_user(conv_id, **kwargs):
            return {"id": 10, "role": "user", "content": "질문"}

        async def fake_path(conv_id, **kwargs):
            return [{"role": "user", "content": "질문"}]

        async def fake_resolve(model_name):
            return _resolved(model_name=model_name, provider_name="openai")

        async def fake_stream(**kwargs):
            yield {"type": "token", "text": "새 답변"}
            yield {"type": "usage", "usage": None}

        added = []

        async def fake_add(conv_id, **kwargs):
            added.append(kwargs)
            return {"id": 20 + len(added)}

        captured = {}

        async def fake_apply(**kwargs):
            captured.update(kwargs)
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "find_turn_start_user", fake_turn_user)
        monkeypatch.setattr(cs, "path_ending_at", fake_path)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/messages/15/regenerate", json={"model": "gpt-4o"})
        assert resp.status_code == 200
        assert '"done"' in resp.text
        assert captured["model_name"] == "gpt-4o"  # 다른 모델로 재생성
        # 새 assistant 는 parent=turn_user(10) + set_leaf(활성 리프 이동)
        asst = [kw for kw in added if kw.get("role") == "assistant"]
        assert asst and asst[-1]["parent_id"] == 10 and asst[-1]["set_leaf"] is True

    async def test_regenerate_no_turn_user_400(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_turn_user(conv_id, **kwargs):
            return None  # 턴-시작 user 없음

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "find_turn_start_user", fake_turn_user)
        resp = await client.post(f"{_BASE}/c1/messages/15/regenerate", json={})
        assert resp.status_code == 400


class TestTempChat:
    _URL = "/api/v1/chat/temp-completions"

    async def test_temp_not_persisted_but_charges(self, client, monkeypatch):
        """임시 채팅: chat_messages 미기록(add_message 미호출), usage_logs 는 기록(conversation_id=None)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_resolve(model_name):
            return _resolved(model_name=model_name, provider_name="openai")

        added = []

        async def fake_add(conv_id, **kwargs):
            added.append(kwargs)
            return {"id": 1}

        async def fake_stream(**kwargs):
            yield {"type": "token", "text": "임시 답변"}
            yield {"type": "usage", "usage": None}

        captured = {}

        async def fake_apply(**kwargs):
            captured.update(kwargs)
            return Decimal("1")

        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(
            self._URL, json={"messages": [{"role": "user", "content": "안녕"}], "model": "gpt-3.5-turbo"}
        )
        assert resp.status_code == 200
        assert '"done"' in resp.text
        assert added == []  # 미저장
        assert captured["conversation_id"] is None
        assert captured["source"] == "web"
        assert captured["usage_cost"].raw_cost > 0  # 과금은 유지

    async def test_temp_rejects_tool_role(self, client):
        resp = await client.post(self._URL, json={"messages": [{"role": "tool", "content": "x"}]})
        assert resp.status_code == 422  # role 화이트리스트(user|assistant|system) 위반


class TestAgentBinding:
    async def test_agent_injects_system_and_uses_model_params(self, client, monkeypatch):
        """agent_id 바인딩: instructions system 선주입 + 에이전트 모델·temperature 적용."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()  # 대화 자체 모델 없음

        async def fake_path(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_resolve(model_name):
            return _resolved(model_name=model_name, provider_name="openai")

        async def fake_agent(agent_id, **kwargs):
            return {
                "id": agent_id,
                "instructions": "너는 해적처럼 말한다",
                "model_name": "gpt-4o",
                "params": {"temperature": 0.9},
                "mcp_ids": [],
                "tool_ids": [],
            }

        seen = {}

        async def fake_stream(**kwargs):
            seen["messages"] = kwargs.get("messages")
            seen["model"] = kwargs.get("model")
            seen["temperature"] = kwargs.get("temperature")
            yield {"type": "token", "text": "아르"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_path)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(ags, "get_agent_for_run", fake_agent)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "안녕", "agent_id": 7})
        assert resp.status_code == 200
        # 에이전트 instructions 가 system 으로 맨 앞에 주입
        assert seen["messages"][0] == {"role": "system", "content": "너는 해적처럼 말한다"}
        # 에이전트 모델 + params.temperature 적용(요청에 미지정 시)
        assert seen["model"] == "gpt-4o"
        assert seen["temperature"] == 0.9

    async def test_agent_not_accessible_404(self, client, monkeypatch):
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv()

        async def fake_agent(agent_id, **kwargs):
            return None  # 미존재/접근 불가

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(ags, "get_agent_for_run", fake_agent)
        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "hi", "agent_id": 999})
        assert resp.status_code == 404


class TestContextInjection:
    async def test_workspace_and_memory_prepended_as_system(self, client, monkeypatch):
        """프로젝트 지침 + 사용자 메모리가 system 으로 선주입(메모리 → 워크스페이스 순)."""
        monkeypatch.setattr(credit, "precheck", _ok_precheck)

        async def fake_get(conv_id, **kwargs):
            return _conv(workspace_id=3)

        async def fake_path(conv_id, **kwargs):
            return {"messages": [], "active_leaf_id": None}

        async def fake_add(conv_id, **kwargs):
            return {"id": 1}

        async def fake_resolve(model_name):
            return _resolved(model_name=model_name, provider_name="openai")

        async def fake_ws(workspace_id, **kwargs):
            return "이 프로젝트는 FastAPI 규칙을 따른다"

        async def fake_mem(**kwargs):
            return ["사용자는 Python 을 선호", "다크모드 사용"]

        seen = {}

        async def fake_stream(**kwargs):
            seen["messages"] = kwargs.get("messages")
            yield {"type": "token", "text": "네"}
            yield {"type": "usage", "usage": None}

        async def fake_apply(**kwargs):
            return Decimal("1")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        monkeypatch.setattr(cs, "get_active_path", fake_path)
        monkeypatch.setattr(cs, "add_message", fake_add)
        monkeypatch.setattr(ps, "resolve_model", fake_resolve)
        monkeypatch.setattr(ws, "get_instructions_for_run", fake_ws)
        monkeypatch.setattr(ms, "active_contents_for_run", fake_mem)
        monkeypatch.setattr(engine, "stream", fake_stream)
        monkeypatch.setattr(credit, "apply_usage", fake_apply)

        resp = await client.post(f"{_BASE}/c1/completions", json={"message": "안녕", "model": "gpt-3.5-turbo"})
        assert resp.status_code == 200
        msgs = seen["messages"]
        # 순서: 메모리 system → 워크스페이스 system → user
        assert msgs[0]["role"] == "system" and "Python 을 선호" in msgs[0]["content"]
        assert msgs[1]["role"] == "system" and "FastAPI" in msgs[1]["content"]
        assert msgs[-1] == {"role": "user", "content": "안녕"}
