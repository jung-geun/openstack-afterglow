"""Service proxy layer for routing Afterglow API calls to extracted services."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.config import get_settings
from app.services import keystone

if TYPE_CHECKING:
    import openstack

_logger = logging.getLogger(__name__)

EXCLUDED_RESPONSE_HEADERS: set[str] = {
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}

FORWARDED_REQUEST_HEADERS: tuple[str, ...] = (
    "idempotency-key",
    "last-event-id",
    "content-type",
    "accept",
    "range",
    "upload-offset",
    "upload-length",
    "upload-metadata",
    "tus-resumable",
    "upload-checksum",
    "content-length",
)


_SERVICE_OVERRIDE_FIELDS: dict[str, str] = {
    "waygate": "service_waygate_internal_url",
    "drover": "service_drover_internal_url",
    "lumen": "service_lumen_internal_url",
    "palimpsest": "service_palimpsest_internal_url",
}


def _configured_internal_endpoint(service_type: str) -> str | None:
    """Return a trusted deployment override, retaining catalog discovery by default."""
    field_name = _SERVICE_OVERRIDE_FIELDS.get(service_type)
    if field_name is None:
        return None
    endpoint = getattr(get_settings(), field_name, "")
    return endpoint or None


def _get_internal_endpoint(token: str, project_id: str, service_type: str) -> str | None:
    """Resolve a service endpoint from the caller-scoped Keystone catalog."""
    if endpoint := _configured_internal_endpoint(service_type):
        return endpoint
    conn: openstack.connection.Connection | None = None
    try:
        conn = keystone.get_openstack_connection(token, project_id)
        endpoint = conn.session.get_endpoint(service_type=service_type, interface="internal")
        return endpoint.rstrip("/") if endpoint else None
    except Exception as exc:
        _logger.warning("Failed to resolve internal endpoint for %s: %s", service_type, exc)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _get_service_internal_endpoint(service_type: str) -> str | None:
    """Resolve a service endpoint without trusting a machine bearer as Keystone auth."""
    if endpoint := _configured_internal_endpoint(service_type):
        return endpoint
    conn: openstack.connection.Connection | None = None
    try:
        conn = keystone.get_admin_project_connection()
        endpoint = conn.session.get_endpoint(service_type=service_type, interface="internal")
        return endpoint.rstrip("/") if endpoint else None
    except Exception as exc:
        _logger.warning("Failed to resolve service-account endpoint for %s: %s", service_type, exc)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _forwarded_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header_name in FORWARDED_REQUEST_HEADERS:
        value = request.headers.get(header_name)
        if value is not None:
            headers[header_name] = value
    return headers


async def _forward(
    service_type: str,
    request: Request,
    upstream_path: str,
    *,
    endpoint: str | None,
    headers: dict[str, str],
) -> Response:
    if not endpoint:
        return JSONResponse(
            status_code=503,
            content={"detail": f"{service_type} 서비스를 사용할 수 없습니다"},
        )

    clean_path = upstream_path if upstream_path.startswith("/") else f"/{upstream_path}"
    upstream_url = f"{endpoint}{clean_path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    content = request.stream() if request.method in {"POST", "PUT", "PATCH", "DELETE"} else None
    settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        verify=settings.ssl_verify,
    )
    try:
        outgoing = client.build_request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            content=content,
        )
        upstream_response = await client.send(outgoing, stream=True)
    except Exception as exc:
        _logger.warning("Upstream proxy request to %s failed: %s", upstream_url, exc)
        await client.aclose()
        return JSONResponse(
            status_code=503,
            content={"detail": f"{service_type} 서비스를 사용할 수 없습니다"},
        )

    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in upstream_response.headers.multi_items()
        if name.lower() not in EXCLUDED_RESPONSE_HEADERS
    ]

    async def stream_content():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    response = StreamingResponse(stream_content(), status_code=upstream_response.status_code)
    response.raw_headers = raw_headers
    return response


async def proxy(service_type: str, request: Request, upstream_path: str) -> Response:
    """Proxy a browser request using its validated caller-scoped Keystone token."""
    token_info = getattr(request.state, "token_info", None)
    token = token_info.get("token") if token_info else None
    project_id = token_info.get("project_id") if token_info else None
    if not token or not project_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    endpoint = await asyncio.to_thread(_get_internal_endpoint, token, project_id, service_type)
    headers = _forwarded_headers(request)
    headers["x-auth-token"] = token
    headers["x-project-id"] = project_id
    return await _forward(service_type, request, upstream_path, endpoint=endpoint, headers=headers)


async def get_json(service_type: str, request: Request, upstream_path: str) -> Any:
    """Fetch a small authenticated JSON document from an extracted service."""
    token_info = getattr(request.state, "token_info", None)
    token = token_info.get("token") if token_info else None
    project_id = token_info.get("project_id") if token_info else None
    if not token or not project_id:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    endpoint = await asyncio.to_thread(_get_internal_endpoint, token, project_id, service_type)
    if not endpoint:
        raise HTTPException(status_code=503, detail=f"{service_type} 서비스를 사용할 수 없습니다")

    clean_path = upstream_path if upstream_path.startswith("/") else f"/{upstream_path}"
    upstream_url = f"{endpoint}{clean_path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    headers = _forwarded_headers(request)
    headers["x-auth-token"] = token
    headers["x-project-id"] = project_id
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            verify=settings.ssl_verify,
        ) as client:
            response = await client.get(upstream_url, headers=headers)
    except Exception as exc:
        _logger.warning("Upstream JSON request to %s failed: %s", upstream_url, exc)
        raise HTTPException(status_code=503, detail=f"{service_type} 서비스를 사용할 수 없습니다") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail") if isinstance(payload, dict) else None
        except ValueError:
            detail = None
        raise HTTPException(
            status_code=response.status_code,
            detail=detail or f"{service_type} 요청에 실패했습니다",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"{service_type} 응답 형식이 잘못되었습니다") from exc


async def resolve_service_endpoint(service_type: str) -> str | None:
    """Resolve an internal catalog endpoint with Afterglow's service credentials."""
    return await asyncio.to_thread(_get_service_internal_endpoint, service_type)


async def proxy_passthrough(
    service_type: str,
    request: Request,
    upstream_path: str,
    *,
    forward_cookie: bool = False,
) -> Response:
    """Proxy a machine-authenticated route without interpreting its bearer token.

    The service-account catalog resolves the endpoint. ``Authorization`` is forwarded
    verbatim so the extracted service remains the sole authority for machine tokens.
    A browser cookie is forwarded only when the caller opts into a cookie-bound flow.
    """
    endpoint = await resolve_service_endpoint(service_type)
    headers = _forwarded_headers(request)
    authorization = request.headers.get("authorization")
    if authorization is not None:
        headers["authorization"] = authorization
    if forward_cookie:
        cookie = request.headers.get("cookie")
        if cookie is not None:
            headers["cookie"] = cookie
    from app.rate_limit import _get_real_ip

    headers["X-Forwarded-For"] = _get_real_ip(request)
    return await _forward(service_type, request, upstream_path, endpoint=endpoint, headers=headers)


async def proxy_unauthenticated(service_type: str, request: Request, upstream_path: str) -> Response:
    """Proxy an unauthenticated browser route without requiring a Keystone token."""
    endpoint = await resolve_service_endpoint(service_type)
    headers = _forwarded_headers(request)
    from app.rate_limit import _get_real_ip

    headers["X-Forwarded-For"] = _get_real_ip(request)
    return await _forward(service_type, request, upstream_path, endpoint=endpoint, headers=headers)
