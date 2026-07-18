"""Phase 2 LangGraph 그래프(graph.stream) 단위 테스트.

litellm_client.acompletion_stream 을 mock 해 네트워크 없이 검증:
- stream_mode="custom" + get_stream_writer 로 token/usage 이벤트가 순서대로 yield 되는지
- 시작 실패/스트리밍 중 오류 시 error 이벤트
- engine.stream 이 graph.stream 에 위임하는지
"""

from app.services.chat import engine, graph, litellm_client

_MSGS = [{"role": "user", "content": "안녕하세요"}]


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

        events = [ev async for ev in graph.stream(model="gpt-3.5-turbo", messages=_MSGS)]
        types = [e["type"] for e in events]
        assert types.count("token") == 2
        assert events[0] == {"type": "token", "text": "안녕"}
        assert events[1] == {"type": "token", "text": "하세요"}
        assert any(e["type"] == "usage" for e in events)

    async def test_passes_model_params_to_litellm(self, monkeypatch):
        captured = {}

        async def fake_stream(**kwargs):
            captured.update(kwargs)
            return _aiter([_Chunk("x")])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        _ = [
            ev
            async for ev in graph.stream(model="m1", messages=_MSGS, api_base="http://b", api_key="k", max_tokens=100)
        ]
        assert captured["model"] == "m1"
        assert captured["api_base"] == "http://b"
        assert captured["api_key"] == "k"
        assert captured["max_tokens"] == 100

    async def test_error_on_start_failure(self, monkeypatch):
        async def fake_fail(**kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_fail)
        events = [ev async for ev in graph.stream(model="m", messages=_MSGS)]
        assert any(e["type"] == "error" for e in events)
        assert not any(e["type"] == "token" for e in events)

    async def test_error_mid_stream(self, monkeypatch):
        async def bad_iter():
            yield _Chunk("부분")
            raise RuntimeError("mid-stream boom")

        async def fake_stream(**kwargs):
            return bad_iter()

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [ev async for ev in graph.stream(model="m", messages=_MSGS)]
        assert events[0] == {"type": "token", "text": "부분"}
        assert any(e["type"] == "error" for e in events)


class TestEngineDelegates:
    async def test_engine_stream_delegates_to_graph(self, monkeypatch):
        async def fake_stream(**kwargs):
            return _aiter([_Chunk("델타")])

        monkeypatch.setattr(litellm_client, "acompletion_stream", fake_stream)
        events = [ev async for ev in engine.stream(model="gpt-3.5-turbo", messages=_MSGS)]
        assert any(e["type"] == "token" and e["text"] == "델타" for e in events)
