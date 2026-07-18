"""Phase 2 LangGraph 에이전트 그래프(graph.stream) 단위 테스트.

litellm_client.acompletion_stream 을 mock 해 네트워크 없이 검증:
- stream_mode="custom" 로 token/usage 이벤트가 순서대로 yield 되는지
- 시작 실패/스트리밍 중 오류 시 error 이벤트
- **툴 루프**: tool_call 델타 → 테넌트 안전 실행(ToolContext) → 툴 결과 반영 후 최종 답변 스트리밍,
  멀티스텝 usage 합산, tool_call SSE 이벤트
- engine.stream 이 graph.stream 에 위임하는지
"""

from app.services.chat import engine, graph, litellm_client, tool_runtime

_MSGS = [{"role": "user", "content": "안녕하세요"}]


# --- 텍스트 스트리밍 청크 ---
class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content=None, usage=None):
        self.choices = [_Choice(content)]
        self.usage = usage


# --- tool_call 델타 청크 ---
class _ToolFn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _ToolCallDelta:
    def __init__(self, index=0, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _ToolFn(name, arguments)


class _DeltaTC:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _ChoiceTC:
    def __init__(self, delta):
        self.delta = delta


class _ChunkTC:
    def __init__(self, delta, usage=None):
        self.choices = [_ChoiceTC(delta)]
        self.usage = usage


async def _aiter(chunks):
    for c in chunks:
        yield c


class TestGraphStream:
    async def test_emits_tokens_then_usage(self, monkeypatch):
        chunks = [
            _Chunk("안녕"),
            _Chunk("하세요"),
            _Chunk(None, usage={"prompt_tokens": 5, "completion_tokens": 2}),
        ]

        async def fake_stream(**kwargs):
            return _aiter(chunks)

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)

        events = [ev async for ev in graph.stream(model="gpt-3.5-turbo", messages=_MSGS, project_id="p1", user_id="u1")]
        types = [e["type"] for e in events]
        assert types.count("token") == 2
        assert events[0] == {"type": "token", "text": "안녕"}
        usage = [e for e in events if e["type"] == "usage"][-1]
        assert usage["usage"] == {"prompt_tokens": 5, "completion_tokens": 2}

    async def test_error_on_start_failure(self, monkeypatch):
        async def fake_fail(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_fail)
        events = [ev async for ev in graph.stream(model="m", messages=_MSGS, project_id="p1", user_id="u1")]
        assert any(e["type"] == "error" for e in events)
        assert not any(e["type"] == "token" for e in events)


class TestToolLoop:
    async def test_tool_call_executes_tenant_safe_then_streams_final(self, monkeypatch):
        # 1턴: tool_call(list_my_conversations) / 2턴: 최종 텍스트
        first = [
            _ChunkTC(_DeltaTC(tool_calls=[_ToolCallDelta(0, "call_1", "list_my_conversations", "{}")])),
            _ChunkTC(_DeltaTC(), usage={"prompt_tokens": 10, "completion_tokens": 3}),
        ]
        second = [
            _ChunkTC(_DeltaTC(content="대화는")),
            _ChunkTC(_DeltaTC(content=" 3개입니다")),
            _ChunkTC(_DeltaTC(), usage={"prompt_tokens": 20, "completion_tokens": 5}),
        ]
        responses = [first, second]
        calls = {"n": 0}

        async def fake_stream(**kwargs):
            idx = calls["n"]
            calls["n"] += 1
            return _aiter(responses[idx])

        captured = {}

        async def fake_execute(name, args, ctx):
            captured["name"] = name
            captured["project_id"] = ctx.project_id
            captured["user_id"] = ctx.user_id
            return "대화 3개"

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        monkeypatch.setattr(tool_runtime, "context_execute", fake_execute)

        events = [ev async for ev in graph.stream(model="m", messages=_MSGS, project_id="p1", user_id="u1")]

        # tool_call 이벤트 + 테넌트 컨텍스트 전달(LLM 인자 아님)
        assert any(e["type"] == "tool_call" and e["name"] == "list_my_conversations" for e in events)
        assert captured["project_id"] == "p1"
        assert captured["user_id"] == "u1"
        # 툴 실행 후 최종 답변 스트리밍
        text = "".join(e["text"] for e in events if e["type"] == "token")
        assert text == "대화는 3개입니다"
        # 멀티스텝 usage 합산 (10+20, 3+5)
        usage = [e for e in events if e["type"] == "usage"][-1]
        assert usage["usage"] == {"prompt_tokens": 30, "completion_tokens": 8}


class TestEngineDelegates:
    async def test_engine_stream_delegates_to_graph(self, monkeypatch):
        async def fake_stream(**kwargs):
            return _aiter([_Chunk("델타")])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [
            ev async for ev in engine.stream(model="gpt-3.5-turbo", messages=_MSGS, project_id="p1", user_id="u1")
        ]
        assert any(e["type"] == "token" and e["text"] == "델타" for e in events)
