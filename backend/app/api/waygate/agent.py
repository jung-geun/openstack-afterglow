"""Permanent proxy for Waygate agent URLs baked into existing gateway VMs."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.services.service_proxy import proxy_passthrough

router = APIRouter()


def _upstream(server_id: str, action: str) -> str:
    return f"/v1/servers/{server_id}/agent/{action}"


@router.post("/{server_id}/agent/register")
async def register_agent(server_id: str, request: Request) -> Response:
    return await proxy_passthrough("waygate", request, _upstream(server_id, "register"))


@router.get("/{server_id}/agent/desired-state")
async def desired_state(server_id: str, request: Request) -> Response:
    return await proxy_passthrough("waygate", request, _upstream(server_id, "desired-state"))


@router.post("/{server_id}/agent/status")
async def report_status(server_id: str, request: Request) -> Response:
    return await proxy_passthrough("waygate", request, _upstream(server_id, "status"))
