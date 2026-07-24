"""자동 메모리 추출(memory_extract) 단위 테스트 — ADD/UPDATE ops 반영 + id 검증 + 미지정 스킵."""

from __future__ import annotations

from decimal import Decimal

from app.services.chat import memory_extract as me


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _Resp:
    def __init__(self, content):
        self.choices = [_Msg(content)]
        self.usage = {"prompt_tokens": 10, "completion_tokens": 5}


class TestParseOps:
    def test_plain_array(self):
        assert me._parse_ops('[{"op":"add","content":"서울 거주"}]') == [{"op": "add", "content": "서울 거주"}]

    def test_code_fence_and_noise(self):
        assert me._parse_ops('설명\n```json\n[{"op":"update","id":3,"content":"x"}]\n```') == [
            {"op": "update", "id": 3, "content": "x"}
        ]

    def test_invalid_returns_empty(self):
        assert me._parse_ops("not json") == []
        assert me._parse_ops("") == []
        assert me._parse_ops('{"op":"add"}') == []  # 배열 아님


class TestGenerateMemory:
    async def test_no_memory_model_skips(self, monkeypatch):
        called = {"acompletion": False}

        async def fake_resolve():
            return None

        async def fake_acompletion(*a, **k):
            called["acompletion"] = True
            return _Resp("[]")

        monkeypatch.setattr(me.ps, "resolve_memory_model", fake_resolve)
        monkeypatch.setattr(me.litellm_client, "acompletion", fake_acompletion)
        await me.generate_memory_if_applicable(conversation_id="c1", project_id="p1", user_id="u1")
        assert called["acompletion"] is False  # 모델 미지정 → 호출 안 함

    async def test_add_and_update_applied_with_id_validation(self, monkeypatch):
        created: list[str] = []
        updated: list[tuple[int, str]] = []

        async def fake_resolve():
            return {
                "model_name": "tiny",
                "provider_name": "p",
                "provider_type": "openai",
                "api_base": None,
                "api_key": "k",
                "margin_multiplier": Decimal("1.0"),
                "input_price_per_token": None,
                "output_price_per_token": None,
                "price_source": None,
            }

        async def fake_list_memories(*, user_id, project_id):
            assert (user_id, project_id) == ("u1", "p1")
            return [{"id": 5, "content": "기존 사실", "is_active": True}]

        async def fake_list_messages(conv_id, *, user_id, project_id, limit=8):
            return [{"role": "user", "content": "나는 커피를 좋아해"}, {"role": "assistant", "content": "알겠어요"}]

        async def fake_acompletion(_model, messages, **_kwargs):
            assert "알겠어요" not in messages[-1]["content"]
            # add 1개 + 유효 update(id 5) + 무효 update(id 999, 무시돼야 함)
            return _Resp(
                '[{"op":"add","content":"커피 선호"},'
                '{"op":"update","id":5,"content":"갱신된 사실"},'
                '{"op":"update","id":999,"content":"소유 아님"}]'
            )

        async def fake_create(*, user_id, project_id, scope, content):
            assert (user_id, project_id, scope) == ("u1", "p1", "project")
            created.append(content)
            return {"id": 1}

        async def fake_update(mid, *, user_id, project_id, patch):
            assert (user_id, project_id) == ("u1", "p1")
            updated.append((mid, patch["content"]))
            return {"id": mid}

        async def fake_apply(**kwargs):
            return Decimal("0")

        monkeypatch.setattr(me.ps, "resolve_memory_model", fake_resolve)
        monkeypatch.setattr(me.ms, "list_memories", fake_list_memories)
        monkeypatch.setattr(me.cs, "list_messages", fake_list_messages)
        monkeypatch.setattr(me.litellm_client, "acompletion", fake_acompletion)
        monkeypatch.setattr(me.ms, "create_memory", fake_create)
        monkeypatch.setattr(me.ms, "update_memory", fake_update)
        monkeypatch.setattr(me.credit, "apply_usage", fake_apply)

        await me.generate_memory_if_applicable(conversation_id="c1", project_id="p1", user_id="u1")

        assert created == ["커피 선호"]
        # id 5 만 반영, id 999(미소유)는 무시
        assert updated == [(5, "갱신된 사실")]
