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

    async def test_emits_reasoning_events(self, monkeypatch):
        """reasoning_content 델타 → reasoning 이벤트(최종 답변 텍스트와 분리)."""

        class _RDelta:
            def __init__(self, content=None, reasoning_content=None):
                self.content = content
                self.reasoning_content = reasoning_content
                self.tool_calls = None

        class _RChunk:
            def __init__(self, delta, usage=None):
                self.choices = [_ChoiceTC(delta)]
                self.usage = usage

        chunks = [
            _RChunk(_RDelta(reasoning_content="단계적으로 생각하면")),
            _RChunk(_RDelta(content="정답은 42")),
            _RChunk(_RDelta(), usage={"prompt_tokens": 3, "completion_tokens": 2}),
        ]

        async def fake_stream(**kwargs):
            return _aiter(chunks)

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [
            ev
            async for ev in graph.stream(
                model="claude-sonnet-5", messages=_MSGS, project_id="p1", user_id="u1", reasoning_effort="low"
            )
        ]
        reasoning = [e for e in events if e["type"] == "reasoning"]
        assert reasoning and reasoning[0]["text"] == "단계적으로 생각하면"
        # 추론 텍스트가 최종 답변 토큰에 섞이지 않아야 함
        tokens = "".join(e["text"] for e in events if e["type"] == "token")
        assert tokens == "정답은 42"

    async def test_emits_citations(self, monkeypatch):
        """Perplexity(search_results/citations) + Gemini(annotations) 출처를 정규화·중복제거해 emit."""

        class _CDelta:
            def __init__(self, content=None, annotations=None):
                self.content = content
                self.annotations = annotations
                self.tool_calls = None

        class _CChunk:
            def __init__(self, delta, citations=None, search_results=None, usage=None):
                self.choices = [_ChoiceTC(delta)]
                self.citations = citations
                self.search_results = search_results
                self.usage = usage

        chunks = [
            _CChunk(
                _CDelta(content="서울과 부산"),
                citations=["https://a.com", "javascript:alert(1)"],  # 비-http 스킴은 걸러져야 함
                search_results=[{"url": "https://a.com", "title": "A", "snippet": "x" * 400}],
            ),
            _CChunk(
                _CDelta(annotations=[{"type": "url_citation", "url_citation": {"url": "https://b.com", "title": "B"}}])
            ),
            _CChunk(_CDelta(), usage={"prompt_tokens": 1, "completion_tokens": 1}),
        ]

        async def fake_stream(**kwargs):
            return _aiter(chunks)

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [
            ev async for ev in graph.stream(model="perplexity/sonar", messages=_MSGS, project_id="p1", user_id="u1")
        ]
        cites = [e for e in events if e["type"] == "citations"]
        assert cites, "citations 이벤트 없음"
        items = cites[-1]["items"]
        assert {i["url"] for i in items} == {"https://a.com", "https://b.com"}
        a = next(i for i in items if i["url"] == "https://a.com")
        assert a["title"] == "A" and len(a["snippet"]) <= 300  # 스니펫 상한
        # citations 는 usage 직전에 나와야 함(최종 답변 저장 타이밍)
        types = [e["type"] for e in events]
        assert types.index("citations") < types.index("usage")

    async def test_no_citations_no_event(self, monkeypatch):
        """출처가 없으면 citations 이벤트를 내지 않는다."""

        async def fake_stream(**kwargs):
            return _aiter([_Chunk("답변"), _Chunk(None, usage={"prompt_tokens": 1, "completion_tokens": 1})])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [ev async for ev in graph.stream(model="gpt-4o", messages=_MSGS, project_id="p1", user_id="u1")]
        assert not any(e["type"] == "citations" for e in events)

    async def test_passes_reasoning_effort(self, monkeypatch):
        captured = {}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            return _aiter([_Chunk("x")])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        _ = [
            ev
            async for ev in graph.stream(
                model="claude-sonnet-5",
                messages=_MSGS,
                project_id="p1",
                user_id="u1",
                reasoning_effort="high",
            )
        ]
        assert captured.get("reasoning_effort") == "high"

    async def test_reasoning_rejection_falls_back_and_caches(self, monkeypatch):
        """reasoning 파라미터 400(예: Claude thinking.type 불일치) → reasoning 없이 재시도해 채팅 유지 +
        해당 모델을 캐시해 이후 요청은 처음부터 reasoning 생략."""
        model = "claude-fallback-test"
        graph._REASONING_UNSUPPORTED.discard(model)  # 격리
        calls: list = []

        async def fake_stream(**kwargs):
            calls.append(kwargs.get("reasoning_effort"))
            if kwargs.get("reasoning_effort"):
                raise RuntimeError("thinking.type.enabled is not supported for this model")
            return _aiter([_Chunk("답변"), _Chunk(None, usage={"prompt_tokens": 1, "completion_tokens": 1})])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [
            ev
            async for ev in graph.stream(
                model=model, messages=_MSGS, project_id="p1", user_id="u1", reasoning_effort="low"
            )
        ]
        # 재시도로 정상 응답, error 이벤트 없음
        assert any(e["type"] == "token" for e in events)
        assert not any(e["type"] == "error" for e in events)
        assert calls == ["low", None]  # 첫 시도(reasoning) → 재시도(reasoning 없이)
        assert model in graph._REASONING_UNSUPPORTED

        # 캐시 이후: 다음 요청은 처음부터 reasoning 없이(실패 요청 반복 안 함)
        calls.clear()
        _ = [
            ev
            async for ev in graph.stream(
                model=model, messages=_MSGS, project_id="p1", user_id="u1", reasoning_effort="low"
            )
        ]
        assert calls == [None]
        graph._REASONING_UNSUPPORTED.discard(model)  # 정리

    async def test_error_on_start_failure(self, monkeypatch):
        async def fake_fail(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_fail)
        events = [ev async for ev in graph.stream(model="m", messages=_MSGS, project_id="p1", user_id="u1")]
        assert any(e["type"] == "error" for e in events)
        assert not any(e["type"] == "token" for e in events)

    async def test_passes_custom_llm_provider(self, monkeypatch):
        captured = {}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            return _aiter([_Chunk("x")])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        _ = [
            ev
            async for ev in graph.stream(
                model="claude-3-5-sonnet",
                messages=_MSGS,
                project_id="p1",
                user_id="u1",
                custom_llm_provider="anthropic",
            )
        ]
        assert captured["custom_llm_provider"] == "anthropic"
        assert captured["model"] == "claude-3-5-sonnet"


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

    async def test_falls_back_to_token_estimation_when_round_has_no_usage(self, monkeypatch):
        async def fake_stream(**kwargs):
            return _aiter([_Chunk("fallback")])

        async def fake_schemas(*_):
            return []

        monkeypatch.setattr(graph.litellm_client, "acompletion_stream", fake_stream)
        monkeypatch.setattr(graph.litellm_client, "extract_usage", lambda *_: (9, 3))
        monkeypatch.setattr(graph.tool_runtime, "context_tool_schemas", fake_schemas)

        events = [
            event
            async for event in graph.stream(
                model="m", messages=[{"role": "user", "content": "hi"}], project_id="p1", user_id="u1"
            )
        ]
        usage = [event for event in events if event["type"] == "usage"][-1]
        assert usage["usage"] == {"prompt_tokens": 9, "completion_tokens": 3}
