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
