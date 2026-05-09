"""Prometheus http_sd 타깃 엔드포인트 — GET /api/sd/prometheus/targets."""

from __future__ import annotations

import asyncio
import logging

import openstack as openstack_lib
from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings

_logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_sd_token(request: Request) -> None:
    settings = get_settings()
    expected = settings.monitoring_sd_token
    if not expected:
        raise HTTPException(status_code=503, detail="monitoring_sd_token이 설정되지 않았습니다")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer 토큰이 필요합니다")
    token = auth[len("Bearer ") :]
    if token != expected:
        raise HTTPException(status_code=401, detail="유효하지 않은 SD 토큰")


def _build_admin_conn() -> openstack_lib.connection.Connection:
    """admin 자격으로 admin 프로젝트에 스코프된 연결 반환."""
    s = get_settings()
    return openstack_lib.connect(
        load_envvars=False,
        load_yaml_config=False,
        auth_url=s.os_auth_url,
        auth_type="password",
        username=s.os_username,
        password=s.os_password,
        project_name=s.os_project_name,
        user_domain_name=s.os_user_domain_name,
        project_domain_name=s.os_project_domain_name,
        region_name=s.os_region_name,
        interface=s.os_interface,
        api_timeout=30,
        verify=s.ssl_verify,
    )


def _collect_targets() -> list[dict]:
    """모든 VM의 node_exporter + dcgm_exporter 타깃 그룹 반환.

    admin 연결로 all_tenants 조회.
    node_exporter 그룹: job="node_exporter" label 추가.
    dcgm_exporter 그룹(GPU VM 한정): job="dcgm_exporter" label 유지.
    """
    conn = _build_admin_conn()
    groups: list[dict] = []
    for s in conn.compute.servers(details=True, all_tenants=True):
        flavor_name = ""
        if s.flavor:
            flavor_name = s.flavor.get("original_name") or s.flavor.get("id") or ""
        is_gpu = flavor_name.startswith("gpu.")

        fixed_ips = []
        for net_addrs in (s.addresses or {}).values():
            for addr in net_addrs:
                if addr.get("OS-EXT-IPS:type") == "fixed":
                    fixed_ips.append(addr["addr"])
        if not fixed_ips:
            continue
        ip = fixed_ips[0]

        base_labels = {
            "instance": s.name or s.id,
            "project_id": s.project_id or "",
            "flavor": flavor_name,
            "gpu": "true" if is_gpu else "false",
        }
        groups.append(
            {
                "targets": [f"{ip}:9100"],
                "labels": {**base_labels, "job": "node_exporter"},
            }
        )
        if is_gpu:
            groups.append(
                {
                    "targets": [f"{ip}:9400"],
                    "labels": {**base_labels, "job": "dcgm_exporter"},
                }
            )
    return groups


@router.get("/prometheus/targets")
async def prometheus_sd_targets(request: Request):
    """Prometheus http_sd_config 호환 타깃 목록 반환.

    각 VM의 fixed IP:9100 (node_exporter) + fixed IP:9400 (dcgm_exporter, GPU VM만) 노출.
    인증: Bearer 토큰 (monitoring_sd_token 설정값).
    """
    _verify_sd_token(request)
    try:
        return await asyncio.to_thread(_collect_targets)
    except Exception:
        _logger.exception("SD 타깃 수집 실패")
        raise HTTPException(status_code=503, detail="SD 타깃 수집 실패")
