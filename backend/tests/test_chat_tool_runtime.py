"""툴 런타임(내장 + 동적 커스텀 HTTP 툴) 실행 테스트.

- context_execute 디스패치: 내장 우선, 커스텀 툴, 미등록.
- 커스텀 HTTP 실행: SSRF 차단 시 안전 문자열, 성공 시 응답 요약.
- 동적 스키마: 내장 + 커스텀 병합. 저장소 장애 시 graceful(내장만).
"""

from app.services.chat import conversation_store as cs
from app.services.chat import ssrf, tool_runtime
from app.services.chat.tools import ToolContext

_CTX = ToolContext(project_id="p1", user_id="u1")


class _Resp:
    def __init__(self, status=200, text="hello world"):
        self.status_code = status
        self.text = text


class _Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        return _Resp()

    async def post(self, url, json=None):
        return _Resp(text="posted")


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
        def _block(url):
            raise ssrf.SsrfBlocked("내부 IP")

        monkeypatch.setattr(ssrf, "validate_url", _block)
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "http://169.254.169.254/", "method": "GET"}, {}, _CTX
        )
        assert "허용되지 않은" in out

    async def test_http_error_returns_safe_string(self, monkeypatch):
        monkeypatch.setattr(ssrf, "validate_url", lambda url: url)

        class _BadClient(_Client):
            async def get(self, url, params=None):
                raise RuntimeError("connection refused")

        monkeypatch.setattr("httpx.AsyncClient", _BadClient)
        out = await tool_runtime._execute_custom_http_tool(
            {"name": "x", "url": "https://api.example", "method": "GET"}, {}, _CTX
        )
        assert "오류" in out


class TestSelectionFilter:
    def test_none_all_empty_subset(self):
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        assert tool_runtime._selected(items, None) == items  # None=전체
        assert tool_runtime._selected(items, ()) == []  # 빈=없음
        assert tool_runtime._selected(items, (1, 3)) == [{"id": 1}, {"id": 3}]  # 부분


class TestMcpTools:
    async def test_selected_mcp_tool_prefixed_schema(self, monkeypatch):
        import app.services.chat.extensions_store as es

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False):
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

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False):
            if kind == "mcp":
                return [{"id": 7, "name": "srv", "url": "https://mcp.example/x"}]
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

        async def fake_list_for_user(kind, *, user_id, project_id, active_only=False):
            return []

        monkeypatch.setattr(es, "list_for_user", fake_list_for_user)
        out = await tool_runtime.context_execute("mcp__99__x", {}, _CTX)
        assert "MCP" in out  # 안전한 거부
