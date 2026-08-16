"""Unauthenticated proxy for browser-facing Lumen MCP OAuth callback."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.services.service_proxy import proxy_passthrough

router = APIRouter()


@router.get("/mcp-oauth/callback")
async def proxy_lumen_mcp_oauth_callback(*, request: Request) -> Response:
    return await proxy_passthrough("lumen", request, "/v1/mcp-oauth/callback", forward_cookie=True)
