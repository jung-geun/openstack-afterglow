"""BFF Proxy router for extracted Palimpsest Hub service routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.api.deps import get_token_info
from app.config import get_settings
from app.services.service_proxy import proxy, proxy_unauthenticated

router = APIRouter()

_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def _require_palimpsest_enabled() -> None:
    if not get_settings().service_palimpsest_enabled:
        raise HTTPException(status_code=503, detail="palimpsest 서비스를 사용할 수 없습니다")


@router.api_route(
    "/image-exports/{export_id}/download",
    methods=["GET"],
    dependencies=[Depends(_require_palimpsest_enabled)],
)
async def proxy_palimpsest_token_download(export_id: str, request: Request) -> Response:
    return await proxy_unauthenticated("palimpsest", request, f"/v1/image-exports/{export_id}/download")


@router.api_route(
    "",
    methods=_PROXY_METHODS,
    dependencies=[Depends(_require_palimpsest_enabled), Depends(get_token_info)],
)
@router.api_route(
    "/{path:path}",
    methods=_PROXY_METHODS,
    dependencies=[Depends(_require_palimpsest_enabled), Depends(get_token_info)],
)
async def proxy_palimpsest_hub(path: str = "", *, request: Request) -> Response:
    upstream_path = "/v1/" if not path else f"/v1/{path}"
    return await proxy("palimpsest", request, upstream_path)
