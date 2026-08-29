"""Bidirectional WebSocket relay for Drover-owned K3s cloud shells."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any
from urllib.parse import quote

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.services.service_proxy import join_version_aware_url, resolve_service_endpoint

router = APIRouter()
_logger = logging.getLogger(__name__)


def _websocket_endpoint(endpoint: str) -> str:
    if endpoint.startswith("https://"):
        return f"wss://{endpoint.removeprefix('https://').rstrip('/')}"
    if endpoint.startswith("http://"):
        return f"ws://{endpoint.removeprefix('http://').rstrip('/')}"
    raise ValueError("Drover catalog endpoint must use http or https")


async def _client_to_upstream(client: WebSocket, upstream: Any) -> None:
    try:
        while True:
            message = await client.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                await upstream.send(message["bytes"])
            elif message.get("text") is not None:
                await upstream.send(message["text"])
    except WebSocketDisconnect:
        return


async def _upstream_to_client(upstream: Any, client: WebSocket) -> None:
    try:
        async for message in upstream:
            if isinstance(message, bytes):
                await client.send_bytes(message)
            else:
                await client.send_text(message)
    except websockets.ConnectionClosed:
        return


async def _relay(client: WebSocket, upstream: Any) -> None:
    tasks = {
        asyncio.create_task(_client_to_upstream(client, upstream)),
        asyncio.create_task(_upstream_to_client(upstream, client)),
    }
    _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


def _relay_close(code: int | None, reason: str | None) -> tuple[int, str]:
    safe_code = (
        code if isinstance(code, int) and 1000 <= code <= 4999 and code not in {1004, 1005, 1006, 1015} else 1011
    )
    safe_reason = reason or ""
    while len(safe_reason.encode("utf-8")) > 123:
        safe_reason = safe_reason[:-1]
    return safe_code, safe_reason


@router.websocket("/{cluster_id}/shell")
async def shell_relay(cluster_id: str, websocket: WebSocket) -> None:
    """Relay the opaque one-time ticket and all WebSocket frames to Drover."""
    await websocket.accept()
    endpoint = await resolve_service_endpoint("drover")
    if not endpoint:
        await websocket.close(code=1013, reason="drover unavailable")
        return

    query = websocket.scope.get("query_string", b"").decode("ascii")
    request_path = f"/v1/clusters/{quote(cluster_id, safe='')}/shell"
    if query:
        request_path = f"{request_path}?{query}"
    try:
        base = _websocket_endpoint(endpoint)
        upstream_url = join_version_aware_url(base, request_path)
    except ValueError:
        _logger.error("Drover catalog endpoint is invalid")
        await websocket.close(code=1013, reason="drover unavailable")
        return

    close_code, close_reason = 1000, ""
    try:
        async with websockets.connect(
            upstream_url,
            max_size=2**20,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=10,
        ) as upstream:
            await _relay(websocket, upstream)
            close_code, close_reason = _relay_close(upstream.close_code, upstream.close_reason)
    except Exception as exc:
        _logger.warning("Drover shell relay failed for cluster %s: %s", cluster_id, exc)
        if websocket.client_state == WebSocketState.CONNECTED:
            with suppress(Exception):
                await websocket.close(code=1013, reason="drover unavailable")
        return

    if websocket.client_state == WebSocketState.CONNECTED:
        with suppress(Exception):
            await websocket.close(code=close_code, reason=close_reason)
