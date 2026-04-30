"""Prometheus http_sd 타깃 엔드포인트 — GET /api/sd/prometheus/targets."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_os_conn
from app.config import get_settings
from app.services import nova

_logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_sd_token(request: Request) -> None:
    settings = get_settings()
    expected = settings.monitoring_sd_token
    if not expected:
        raise HTTPException(status_code=503, detail="monitoring_sd_token이 설정되지 않았습니다")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer ") :]
    else:
        token = request.query_params.get("token", "")
    if token != expected:
        raise HTTPException(status_code=401, detail="유효하지 않은 SD 토큰")


@router.get("/prometheus/targets")
async def prometheus_sd_targets(
    request: Request,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Prometheus http_sd_config 호환 타깃 목록 반환.

    각 VM의 fixed IP:9100 (node_exporter) + fixed IP:9400 (dcgm_exporter, GPU VM만)을
    노출한다. 인증은 Bearer 토큰 또는 ?token= 쿼리 파라미터.
    """
    _verify_sd_token(request)

    instances = await asyncio.to_thread(nova.list_servers, conn)

    groups: list[dict] = []
    for inst in instances:
        fixed_ips = [ip.addr for ip in inst.ip_addresses if ip.type == "fixed"]
        if not fixed_ips:
            continue
        ip = fixed_ips[0]
        is_gpu = bool(inst.flavor_name and inst.flavor_name.startswith("gpu."))
        labels = {
            "instance": inst.name,
            "project_id": inst.project_id or "",
            "flavor": inst.flavor_name or "",
            "gpu": "true" if is_gpu else "false",
        }
        groups.append({"targets": [f"{ip}:9100"], "labels": labels})
        if is_gpu:
            groups.append({"targets": [f"{ip}:9400"], "labels": {**labels, "job": "dcgm_exporter"}})

    return groups
