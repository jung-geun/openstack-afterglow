"""Permanent proxy for callback URLs baked into existing K3s control planes."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.services.service_proxy import proxy_passthrough

router = APIRouter()


@router.post("/callback")
async def callback(request: Request) -> Response:
    return await proxy_passthrough("drover", request, "/v1/callback")
