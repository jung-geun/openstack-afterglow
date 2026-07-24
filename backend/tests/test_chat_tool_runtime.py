"""툴 런타임(내장 + 동적 커스텀 HTTP 툴) 실행 테스트.

- context_execute 디스패치: 내장 우선, 커스텀 툴, 미등록.
- 커스텀 HTTP 실행: SSRF 차단 시 안전 문자열, 성공 시 응답 요약.
- 동적 스키마: 내장 + 커스텀 병합. 저장소 장애 시 graceful(내장만).
"""

import json

from app.services.chat import conversation_store as cs
from app.services.chat import ssrf, tool_runtime
from app.services.chat.tools import ToolContext

_CTX = ToolContext(project_id="p1", user_id="u1")


class _Resp:
    def __init__(self, status=200, text="hello world"):
        self.status_code = status
        self._text = text
        self.encoding = "utf-8"
        self.headers = {}

    async def aiter_bytes(self):
        yield self._text.encode()


class _Stream:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        return False


class _Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url, **kwargs):
        return _Stream(_Resp(text="posted" if method == "POST" else "hello world"))


class _ManagedHooks:
    def __init__(self, allowed: bool = True):
        self.allowed = allowed
        self.calls: list[tuple[str, int]] = []

    async def managed_tool_allowed(self, *, tool_name: str, maximum: int) -> bool:
        self.calls.append((tool_name, maximum))
        return self.allowed


class TestSchemas:
    async def test_builtin_plus_custom(self, monkeypatch):
        async def fake_load(ctx):
            return [{"name": "weather", "description": "날씨", "params_schema": None}]

        monkeypatch.setattr(tool_runtime, "_load_custom", fake_load)
        schemas = await tool_runtime.context_tool_schemas(_CTX)
        names = {s["function"]["name"] for s in schemas}
        assert "list_my_conversations" in names  # 내장
        assert "weather" in names  # 커스텀

    async def test_graceful_when_storage_fails(self, monkeypatch):
        # _load_custom 내부 예외 → 내장 툴만 (graph 가 죽지 않게)
        schemas = await tool_runtime.context_tool_schemas(_CTX)  # 실 DB 없음 → graceful
        names = {s["function"]["name"] for s in schemas}
        assert "list_my_conversations" in names


class TestManagedTools:
    async def test_managed_tools_are_gated_by_durable_hook_and_emit_schemas(self, monkeypatch):
        async def no_custom(ctx):
            return []

        monkeypatch.setattr(tool_runtime, "_load_custom", no_custom)
        hooks = _ManagedHooks()
        ctx = ToolContext(
            project_id="p1",
            user_id="u1",
            execution_hooks=hooks,
            managed_search={
                "route": {"provider_type": "perplexity"},
                "options": {"max_uses": 2, "context_size": "low"},
            },
            managed_fetch={"max_uses": 1},
        )
        names = {schema["function"]["name"] for schema in await tool_runtime.context_tool_schemas(ctx)}
        assert {"managed_web_search", "managed_web_fetch"} <= names

        async def fake_search(*args, **kwargs):
            return [tool_runtime.web_search.SearchCitation(url="https://docs.example/a", title="A", snippet="B")]

        monkeypatch.setattr(tool_runtime.web_search, "search_with_route", fake_search)
        result = await tool_runtime.context_execute("managed_web_search", {"query": "docs"}, ctx)
        assert json.loads(result)["sources"][0]["url"] == "https://docs.example/a"
        assert hooks.calls == [("managed_web_search", 2)]

    async def test_managed_tool_limit_stops_before_provider_io(self, monkeypatch):
        hooks = _ManagedHooks(allowed=False)
        ctx = ToolContext(
            project_id="p1",
            user_id="u1",
            execution_hooks=hooks,
            managed_search={
                "route": {"provider_type": "perplexity"},
                "options": {"max_uses": 1, "context_size": "low"},
            },
        )

        async def unexpected(*args, **kwargs):
            raise AssertionError("provider must not be called after durable limit")

        monkeypatch.setattr(tool_runtime.web_search, "search_with_route", unexpected)
        assert "한도" in await tool_runtime.context_execute("managed_web_search", {"query": "docs"}, ctx)

    def test_managed_search_result_is_bounded_for_multibyte_content(self):
        result = tool_runtime._bounded_search_result(
            [
                tool_runtime.web_search.SearchCitation(
                    url="https://docs.example/a", title="제목" * 1_000, snippet="한글" * 30_000
                )
            ]
        )
        assert len(result.encode("utf-8")) <= tool_runtime._MAX_MANAGED_RESULT_BYTES

    async def test_managed_advisor_result_stays_private_from_graph_projection(self, monkeypatch):
        async def no_custom(ctx):
            return []

        monkeypatch.setattr(tool_runtime, "_load_custom", no_custom)
        hooks = _ManagedHooks()
        ctx = ToolContext(
            project_id="p1",
            user_id="u1",
            execution_hooks=hooks,
            managed_advisor={
                "route": {"model_name": "advisor-model"},
                "options": {"max_uses": 2},
            },
            advisor_visible_messages=({"role": "user", "content": "visible context"},),
        )

        class _Result:
            advice = "private advice"
            prompt_tokens = 3
            completion_tokens = 2

        async def fake_advisor(**kwargs):
            assert kwargs["visible_messages"] == [{"role": "user", "content": "visible context"}]
            return _Result()

        monkeypatch.setattr(tool_runtime.advisor, "ask_with_route", fake_advisor)
        names = {schema["function"]["name"] for schema in await tool_runtime.context_tool_schemas(ctx)}
        assert "managed_advisor" in names
        result = await tool_runtime.context_execute_result("managed_advisor", {"goal": "review"}, ctx)
        assert result.content == "private advice"
        assert result.visible is False
        assert hooks.calls == [("managed_advisor", 2)]


class TestDispatch:
    async def test_builtin_dispatch(self, monkeypatch):
        async def fake_list(**kwargs):
            return [{"id": "c1", "title": "t", "model_name": "m"}]

        monkeypatch.setattr(cs, "list_conversations", fake_list)
        out = await tool_runtime.context_execute("list_my_conversations", {}, _CTX)
        assert "t" in out

    async def test_unknown_tool(self, monkeypatch):
        async def fake_load(ctx):
            return []

        monkeypatch.setattr(tool_runtime, "_load_custom", fake_load)
        out = await tool_runtime.context_execute("no_such", {}, _CTX)
        assert "알 수 없는" in out

    async def test_custom_tool_dispatch_success(self, monkeypatch):
        async def fake_load(ctx):
            return [{"name": "weather", "method": "GET", "url": "https://api.example/w", "timeout_seconds": 5}]

        monkeypatch.setattr(tool_runtime, "_load_custom", fake_load)
        monkeypatch.setattr(ssrf, "validate_url", lambda url: url)  # SSRF 통과
        monkeypatch.setattr("httpx.AsyncClient", _Client)
        out = await tool_runtime.context_execute("weather", {"city": "seoul"}, _CTX)
        assert out.startswith("[200]")
        assert "hello world" in out


class TestCustomExecution:
    async def test_ssrf_blocked_returns_safe_string(self, monkeypatch):
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "http://169.254.169.254/", "method": "GET"}, {}, _CTX
        )
        assert "허용되지 않은" in out

    async def test_http_error_returns_safe_string(self, monkeypatch):
        class _BadClient(_Client):
            def stream(self, method, url, **kwargs):
                raise RuntimeError("connection refused")

        monkeypatch.setattr("httpx.AsyncClient", _BadClient)
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "https://api.example", "method": "GET"}, {}, _CTX
        )
        assert "오류" in out

    async def test_large_http_response_is_not_materialized(self, monkeypatch):
        class _LargeResponse(_Resp):
            async def aiter_bytes(self):
                yield b"x" * (tool_runtime._MAX_RESPONSE_BYTES + 1)

        class _LargeClient(_Client):
            def stream(self, method, url, **kwargs):
                return _Stream(_LargeResponse())

        monkeypatch.setattr("httpx.AsyncClient", _LargeClient)
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "https://api.example", "method": "GET"}, {}, _CTX
        )
        assert "허용 크기" in out

    async def test_compressed_http_response_is_rejected_before_iteration(self, monkeypatch):
        class _CompressedResponse(_Resp):
            def __init__(self):
                super().__init__()
                self.headers = {"content-encoding": "gzip"}

            async def aiter_bytes(self):
                raise AssertionError("compressed content must not be decompressed")
                yield b""  # pragma: no cover

        class _CompressedClient(_Client):
            def stream(self, method, url, **kwargs):
                return _Stream(_CompressedResponse())

        monkeypatch.setattr("httpx.AsyncClient", _CompressedClient)
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "https://api.example", "method": "GET"}, {}, _CTX
        )
        assert "압축된" in out


class TestSelectionFilter:
    def test_none_all_empty_subset(self):
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        assert tool_runtime._selected(items, None) == items  # None=전체
        assert tool_runtime._selected(items, ()) == []  # 빈=없음
        assert tool_runtime._selected(items, (1, 3)) == [{"id": 1}, {"id": 3}]  # 부분


class TestMcpTools:
    async def test_selected_mcp_tool_prefixed_schema(self, monkeypatch):
        import app.services.chat.extensions_store as es

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False, reveal_secrets=False):
            if kind == "mcp":
                return [{"id": 7, "name": "srv", "transport": "http", "url": "https://mcp.example/x"}]
            return []  # 커스텀 tool 없음

        async def fake_list_tools(server):
            return [{"name": "search", "description": "d", "input_schema": {"type": "object"}}]

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        monkeypatch.setattr(tool_runtime.mcp_client, "list_tools", fake_list_tools)
        schemas = await tool_runtime.context_tool_schemas(_CTX)
        names = {s["function"]["name"] for s in schemas}
        assert "mcp__7__search" in names  # server_id 접두

    async def test_mcp_name_routes_to_call_tool(self, monkeypatch):
        import app.services.chat.extensions_store as es

        captured = {}

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False, reveal_secrets=False):
            if kind == "mcp":
                return [{"id": 7, "name": "srv", "transport": "http", "url": "https://mcp.example/x"}]
            return []

        async def fake_call_tool(server, tool_name, args):
            captured.update(server_id=server["id"], tool=tool_name, args=args)
            return "결과"

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        monkeypatch.setattr(tool_runtime.mcp_client, "call_tool", fake_call_tool)
        out = await tool_runtime.context_execute("mcp__7__search", {"q": "x"}, _CTX)
        assert out == "결과"
        assert captured == {"server_id": 7, "tool": "search", "args": {"q": "x"}}

    async def test_mcp_unknown_server_safe_string(self, monkeypatch):
        import app.services.chat.extensions_store as es

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False, reveal_secrets=False):
            return []

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        out = await tool_runtime.context_execute("mcp__99__x", {}, _CTX)
        assert "MCP" in out  # 안전한 거부

    async def test_legacy_mcp_transport_is_not_exposed(self, monkeypatch):
        import app.services.chat.extensions_store as es

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False, reveal_secrets=False):
            return [{"id": 7, "name": "legacy", "transport": "sse", "url": "https://mcp.example/sse"}]

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        assert await tool_runtime._load_mcp(_CTX) == []

    async def test_unsatisfied_requirement_server_skipped(self, monkeypatch):
        """사용자 인증 요구사항 미충족 서버는 노출되지 않고(스킵), 값 채우면 병합되어 노출된다."""
        import app.services.chat.extensions_store as es

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False, reveal_secrets=False):
            if kind == "mcp":
                return [
                    {
                        "id": 7,
                        "name": "notion",
                        "transport": "http",
                        "url": "https://mcp.example",
                        "headers": {},
                        "auth_requirements": [{"key": "Authorization"}],
                    }
                ]
            return []

        # 값 없음 → 스킵.
        async def no_creds(*, user_id, project_id):
            return {}

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        monkeypatch.setattr(es, "mcp_all_credentials", no_creds)
        assert await tool_runtime._load_mcp(_CTX) == []

        # 사용자 값 채움 → 병합되어 노출 + 헤더에 반영.
        async def with_creds(*, user_id, project_id):
            return {7: {"Authorization": "Bearer mine"}}

        monkeypatch.setattr(es, "mcp_all_credentials", with_creds)
        servers = await tool_runtime._load_mcp(_CTX)
        assert len(servers) == 1
        assert servers[0]["headers"]["Authorization"] == "Bearer mine"
