from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from starlette.websockets import WebSocketState

from app.api import k3s_shell_proxy
from app.api.k3s_shell_proxy import _client_to_upstream, _upstream_to_client, _websocket_endpoint


class _ClientInput:
    def __init__(self):
        self.messages = iter(
            (
                {"type": "websocket.receive", "bytes": b"\x00stdin", "text": None},
                {"type": "websocket.receive", "bytes": None, "text": "resize"},
                {"type": "websocket.disconnect"},
            )
        )

    async def receive(self):
        return next(self.messages)


class _UpstreamOutput:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


class _UpstreamInput:
    def __init__(self):
        self.messages = iter((b"\x01stdout", "status"))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _ClientOutput:
    def __init__(self):
        self.bytes = []
        self.text = []

    async def send_bytes(self, message):
        self.bytes.append(message)

    async def send_text(self, message):
        self.text.append(message)


async def test_client_frames_are_forwarded_without_reencoding():
    upstream = _UpstreamOutput()
    await _client_to_upstream(_ClientInput(), upstream)
    assert upstream.sent == [b"\x00stdin", "resize"]


async def test_upstream_frames_preserve_binary_and_text_types():
    client = _ClientOutput()
    await _upstream_to_client(_UpstreamInput(), client)
    assert client.bytes == [b"\x01stdout"]
    assert client.text == ["status"]


def test_catalog_endpoint_is_converted_to_websocket_scheme():
    assert _websocket_endpoint("http://drover.internal:8011/") == "ws://drover.internal:8011"
    assert _websocket_endpoint("https://drover.example/") == "wss://drover.example"


class _RelayClient:
    def __init__(self):
        self.scope = {"query_string": b"ticket=opaque-ticket"}
        self.client_state = WebSocketState.CONNECTING
        self.closed = None

    async def accept(self):
        self.client_state = WebSocketState.CONNECTED

    async def close(self, *, code, reason=""):
        self.closed = (code, reason)
        self.client_state = WebSocketState.DISCONNECTED


class _ClosedUpstream:
    close_code = 4408
    close_reason = "idle timeout"


class _ConnectContext:
    async def __aenter__(self):
        return _ClosedUpstream()

    async def __aexit__(self, *_args):
        return None


async def test_shell_relay_propagates_drover_idle_timeout(monkeypatch):
    client = _RelayClient()
    connect = MagicMock(return_value=_ConnectContext())
    monkeypatch.setattr(k3s_shell_proxy, "resolve_service_endpoint", AsyncMock(return_value="http://drover:8011"))
    monkeypatch.setattr(k3s_shell_proxy.websockets, "connect", connect)
    monkeypatch.setattr(k3s_shell_proxy, "_relay", AsyncMock())

    await k3s_shell_proxy.shell_relay("cluster-1", client)

    assert connect.call_args.args[0] == ("ws://drover:8011/v1/clusters/cluster-1/shell?ticket=opaque-ticket")
    assert client.closed == (4408, "idle timeout")
