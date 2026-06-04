"""Prometheus http_sd 타깃 엔드포인트 — GET /api/sd/prometheus/targets."""

from __future__ import annotations

import logging

import openstack as openstack_lib
from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.services.cache import cached_call, ttl_slow

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

    admin 연결로 all_tenants 조회. limit=100으로 페이지 크기를 제한하며
    openstacksdk가 자동 페이지네이션으로 전체 결과를 순회한다.
    """
    settings = get_settings()
    conn = _build_admin_conn()
    groups: list[dict] = []
    for s in conn.compute.servers(details=True, all_tenants=True, limit=100):
        flavor_name = ""
        if s.flavor:
            flavor_name = s.flavor.get("original_name") or s.flavor.get("id") or ""
        is_gpu = flavor_name.startswith(settings.gpu_flavor_prefix)

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
                "targets": [f"{ip}:{settings.node_exporter_port}"],
                "labels": {**base_labels, "job": "node_exporter"},
            }
        )
        if is_gpu:
            groups.append(
                {
                    "targets": [f"{ip}:{settings.dcgm_exporter_port}"],
                    "labels": {**base_labels, "job": "dcgm_exporter"},
                }
            )
    return groups


def _collect_libvirt_targets() -> list[dict]:
    """모든 compute 노드의 libvirt_exporter 타깃 반환.

    Nova admin 연결로 hypervisors 목록을 조회, host_ip:libvirt_exporter_port 를 단일 그룹으로 노출.
    libvirt_exporter가 hypervisor 측에서 실행되므로 게스트 OS의 node_exporter 설치 여부와 무관하게
    모든 VM의 메트릭을 커버한다.
    """
    settings = get_settings()
    conn = _build_admin_conn()
    targets: list[str] = []
    for hv in conn.compute.hypervisors(details=True):
        host_ip = getattr(hv, "host_ip", None) or hv.name
        if host_ip:
            targets.append(f"{host_ip}:{settings.libvirt_exporter_port}")
    return [{"targets": targets, "labels": {"job": "libvirt_exporter"}}] if targets else []


@router.get("/prometheus/targets")
async def prometheus_sd_targets(request: Request):
    """Prometheus http_sd_config 호환 타깃 목록 반환.

    각 VM의 fixed IP:node_exporter_port + fixed IP:dcgm_exporter_port (GPU VM만) 노출.
    60초 Redis 캐시로 Nova 호출 부하를 제어한다.
    인증: Bearer 토큰 (monitoring_sd_token 설정값).
    """
    _verify_sd_token(request)
    try:
        return await cached_call(
            "afterglow:sd:prometheus:targets",
            ttl_slow(),
            _collect_targets,
        )
    except HTTPException:
        raise
    except Exception:
        _logger.exception("SD 타깃 수집 실패")
        raise HTTPException(status_code=503, detail="SD 타깃 수집 실패")


@router.get("/prometheus/libvirt-targets")
async def prometheus_libvirt_sd_targets(request: Request):
    """Prometheus http_sd_config 호환 libvirt_exporter 타깃 목록 반환.

    compute 노드별 host_ip:libvirt_exporter_port 를 단일 그룹으로 노출.
    kolla `enable_prometheus_libvirt_exporter: yes` 설정 후 reconfigure 필요.
    인증: Bearer 토큰 (monitoring_sd_token 설정값).
    """
    _verify_sd_token(request)
    try:
        return await cached_call(
            "afterglow:sd:prometheus:libvirt-targets",
            ttl_slow(),
            _collect_libvirt_targets,
        )
    except HTTPException:
        raise
    except Exception:
        _logger.exception("libvirt SD 타깃 수집 실패")
        raise HTTPException(status_code=503, detail="libvirt SD 타깃 수집 실패")
