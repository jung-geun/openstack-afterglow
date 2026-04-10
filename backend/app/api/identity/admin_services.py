"""관리자 서비스 상태 모니터링 엔드포인트."""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn, require_admin
from app.config import get_settings
from app.services.cache import cached_call, ttl_normal

_logger = logging.getLogger(__name__)

router = APIRouter()

_SERVICE_TIMEOUT = 12  # 서비스별 조회 타임아웃 (초)

VALID_CATEGORIES = {
    "compute", "block_storage", "network", "shared_file_system",
    "orchestration", "container", "container_infra", "endpoints", "storage_pools",
}


def _get_ep(conn: openstack.connection.Connection, service_type: str, interface: str = "public") -> str | None:
    """서비스 카탈로그에서 endpoint URL 조회. 없으면 None 반환."""
    try:
        ep = conn.session.get_endpoint(service_type=service_type, interface=interface)
        return ep.rstrip("/") if ep else None
    except Exception:
        return None


def _strip_version(url: str) -> str:
    """URL 끝의 /vN[.M] 및 선택적 /{project_id}를 제거하여 base URL 반환.
    예: http://host:8786/v2/abc123 → http://host:8786
        http://host:9292/v2.0     → http://host:9292
    """
    return re.sub(r'/v[0-9.]+(?:/[a-f0-9\-]+)?$', '', url.rstrip('/'))


# ---------------------------------------------------------------------------
# 카테고리별 독립 조회 함수
# ---------------------------------------------------------------------------

def _fetch_compute(conn) -> list[dict]:
    result = []
    try:
        for svc in conn.compute.services():
            result.append({
                "id": getattr(svc, "id", ""),
                "binary": svc.binary or "",
                "host": svc.host or "",
                "status": svc.status or "",
                "state": svc.state or "",
                "zone": getattr(svc, "zone", ""),
                "updated_at": str(svc.updated_at) if getattr(svc, "updated_at", None) else None,
                "disabled_reason": getattr(svc, "disabled_reason", None),
            })
    except Exception:
        _logger.warning("Nova 서비스 조회 실패", exc_info=True)
    return result


def _fetch_block_storage(conn) -> list[dict]:
    result = []
    try:
        for svc in conn.block_storage.services():
            result.append({
                "id": getattr(svc, "id", ""),
                "binary": svc.binary or "",
                "host": svc.host or "",
                "status": svc.status or "",
                "state": svc.state or "",
                "zone": getattr(svc, "zone", ""),
                "updated_at": str(svc.updated_at) if getattr(svc, "updated_at", None) else None,
                "disabled_reason": getattr(svc, "disabled_reason", None),
            })
    except Exception:
        _logger.warning("Cinder 서비스 조회 실패", exc_info=True)
    return result


def _fetch_network(conn) -> list[dict]:
    result = []
    try:
        network_ep = _get_ep(conn, "network")
        if network_ep:
            network_ep = _strip_version(network_ep)
            net_resp = conn.session.get(f"{network_ep}/v2.0/agents", timeout=_SERVICE_TIMEOUT)
            for agent in net_resp.json().get("agents", []):
                result.append({
                    "id": agent.get("id", ""),
                    "binary": agent.get("binary", ""),
                    "host": agent.get("host", ""),
                    "agent_type": agent.get("agent_type", ""),
                    "availability_zone": agent.get("availability_zone") or None,
                    "alive": agent.get("alive", False),
                    "admin_state_up": agent.get("admin_state_up", True),
                    "updated_at": agent.get("heartbeat_timestamp") or agent.get("last_heartbeat_at") or agent.get("updated_at") or None,
                })
    except Exception:
        _logger.warning("Neutron 에이전트 조회 실패", exc_info=True)
    return result


def _fetch_shared_file_system(conn, settings) -> list[dict]:
    result = []
    if not settings.service_manila_enabled:
        return result
    try:
        manila_ep = _get_ep(conn, "shared-file-system")
        if manila_ep:
            project_id = conn.current_project_id or getattr(conn, '_union_project_id', '')
            manila_base = _strip_version(manila_ep)
            resp = conn.session.get(f"{manila_base}/v2/{project_id}/os-services", timeout=_SERVICE_TIMEOUT)
            for svc in resp.json().get("services", []):
                result.append({
                    "id": svc.get("id", ""),
                    "binary": svc.get("binary", ""),
                    "host": svc.get("host", ""),
                    "status": svc.get("status", ""),
                    "state": svc.get("state", ""),
                    "zone": svc.get("zone", ""),
                    "updated_at": svc.get("updated_at") or None,
                    "disabled_reason": svc.get("disabled_reason") or None,
                })
    except Exception:
        _logger.warning("Manila 서비스 조회 실패", exc_info=True)
    return result


def _fetch_orchestration(conn, settings) -> list[dict]:
    result = []
    if not settings.service_magnum_enabled:
        return result
    try:
        heat_ep = _get_ep(conn, "orchestration")
        if heat_ep:
            project_id = conn.current_project_id or getattr(conn, '_union_project_id', '')
            heat_base = _strip_version(heat_ep)
            resp = conn.session.get(f"{heat_base}/v1/{project_id}/services", timeout=_SERVICE_TIMEOUT)
            for svc in resp.json().get("services", []):
                _raw = svc.get("status", "")
                result.append({
                    "id": svc.get("id", ""),
                    "binary": svc.get("binary", ""),
                    "host": svc.get("host", ""),
                    "status": "enabled" if _raw == "up" else ("disabled" if _raw == "down" else _raw),
                    "state": svc.get("engine_status", ""),
                    "zone": "",
                    "updated_at": svc.get("updated_at") or None,
                    "disabled_reason": None,
                })
    except Exception:
        _logger.warning("Heat 서비스 조회 실패", exc_info=True)
    return result


def _fetch_container(conn, settings) -> list[dict]:
    result = []
    if not settings.service_zun_enabled:
        return result
    try:
        zun_ep = _get_ep(conn, "container")
        if zun_ep:
            zun_ep = _strip_version(zun_ep)
            resp = conn.session.get(f"{zun_ep}/v1/services", timeout=_SERVICE_TIMEOUT)
            for svc in resp.json().get("services", []):
                _raw = svc.get("status", "")
                result.append({
                    "id": svc.get("id", ""),
                    "binary": svc.get("binary", ""),
                    "host": svc.get("host", ""),
                    "status": "enabled" if _raw == "up" else ("disabled" if _raw == "down" else _raw),
                    "state": svc.get("state", ""),
                    "zone": svc.get("availability_zone", ""),
                    "updated_at": svc.get("updated_at") or None,
                    "disabled_reason": None,
                })
    except Exception:
        _logger.warning("Zun 서비스 조회 실패", exc_info=True)
    return result


def _fetch_container_infra(conn, settings) -> list[dict]:
    result = []
    if not settings.service_magnum_enabled:
        return result
    try:
        magnum_ep = _get_ep(conn, "container-infra")
        if magnum_ep:
            magnum_base = _strip_version(magnum_ep)
            resp = conn.session.get(f"{magnum_base}/v1/mservices", timeout=_SERVICE_TIMEOUT)
            for svc in resp.json().get("mservices", []):
                result.append({
                    "id": svc.get("id", ""),
                    "binary": svc.get("binary", ""),
                    "host": svc.get("host", ""),
                    "status": "disabled" if svc.get("disabled", False) else "enabled",
                    "state": svc.get("state", ""),
                    "zone": "",
                    "updated_at": svc.get("updated_at") or None,
                    "disabled_reason": svc.get("disabled_reason") or None,
                })
    except Exception:
        _logger.warning("Magnum 서비스 조회 실패", exc_info=True)
    return result


def _fetch_endpoints(conn) -> list[dict]:
    result = []
    try:
        svc_map: dict[str, dict] = {}
        for svc in conn.identity.services():
            svc_map[svc.id] = {
                "name": svc.name or "",
                "type": svc.type or "",
            }
        grouped: dict[str, dict] = {}
        for ep in conn.identity.endpoints():
            sid = ep.service_id or ""
            if sid not in grouped:
                svc_info = svc_map.get(sid, {})
                grouped[sid] = {
                    "service_id": sid,
                    "name": svc_info.get("name", ""),
                    "service": svc_info.get("type", ""),
                    "region": getattr(ep, "region_id", "") or getattr(ep, "region", "") or "",
                    "endpoints": {},
                }
            iface = ep.interface or ""
            grouped[sid]["endpoints"][iface] = ep.url or ""
        result = list(grouped.values())
    except Exception:
        _logger.warning("Keystone endpoint 조회 실패", exc_info=True)
    return result


def _fetch_storage_pools(conn) -> list[dict]:
    result = []
    try:
        bs_ep = conn.block_storage.get_endpoint()
        pools_resp = conn.session.get(f"{bs_ep}/scheduler-stats/get_pools", params={"detail": "True"}, timeout=_SERVICE_TIMEOUT)
        for pool in pools_resp.json().get("pools", []):
            caps = pool.get("capabilities", {})
            total_gb = caps.get("total_capacity_gb", 0)
            free_gb = caps.get("free_capacity_gb", 0)
            allocated_gb = caps.get("allocated_capacity_gb", 0)
            if isinstance(total_gb, str):
                total_gb = float(total_gb) if total_gb not in ("infinite", "unknown", None) else 0
            if isinstance(free_gb, str):
                free_gb = float(free_gb) if free_gb not in ("infinite", "unknown", None) else 0
            result.append({
                "name": pool.get("name", ""),
                "volume_backend_name": caps.get("volume_backend_name", ""),
                "driver_version": caps.get("driver_version", ""),
                "storage_protocol": caps.get("storage_protocol", ""),
                "vendor_name": caps.get("vendor_name", ""),
                "total_capacity_gb": round(float(total_gb), 2),
                "free_capacity_gb": round(float(free_gb), 2),
                "allocated_capacity_gb": round(float(allocated_gb), 2) if allocated_gb else 0,
            })
    except Exception:
        _logger.warning("Cinder storage pools 조회 실패", exc_info=True)
    return result


# ---------------------------------------------------------------------------
# fetch 함수 맵
# ---------------------------------------------------------------------------

def _make_fetch_map(conn, settings):
    return {
        "compute": lambda: _fetch_compute(conn),
        "block_storage": lambda: _fetch_block_storage(conn),
        "network": lambda: _fetch_network(conn),
        "shared_file_system": lambda: _fetch_shared_file_system(conn, settings),
        "orchestration": lambda: _fetch_orchestration(conn, settings),
        "container": lambda: _fetch_container(conn, settings),
        "container_infra": lambda: _fetch_container_infra(conn, settings),
        "endpoints": lambda: _fetch_endpoints(conn),
        "storage_pools": lambda: _fetch_storage_pools(conn),
    }


# ---------------------------------------------------------------------------
# 라우터
# ---------------------------------------------------------------------------

@router.get("/services", dependencies=[Depends(require_admin)])
async def list_services(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
    category: str | None = Query(None),
):
    """Nova, Cinder, Neutron, Manila, Heat, Zun, Magnum 서비스 상태 + API Endpoints + Storage Pools 조회.

    category 파라미터가 있으면 해당 카테고리만 조회하고 별도 캐시 키로 캐싱한다.
    category 없으면 전체를 병렬로 조회하여 반환한다.
    """
    settings = get_settings()

    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 카테고리: {category}")
        cache_key = f"union:admin:services:{category}"
        fetch_map = _make_fetch_map(conn, settings)
        fetch_fn = fetch_map[category]

        def _collect_one():
            return {category: fetch_fn()}

        try:
            return await cached_call(cache_key, ttl_normal(), _collect_one, refresh=refresh)
        except Exception:
            raise HTTPException(status_code=500, detail="서비스 상태 조회 실패")

    # 전체 조회: ThreadPoolExecutor로 병렬 실행
    def _collect_all():
        fetch_map = _make_fetch_map(conn, settings)
        result: dict[str, list] = {k: [] for k in VALID_CATEGORIES}

        with ThreadPoolExecutor(max_workers=len(VALID_CATEGORIES)) as executor:
            futures = {executor.submit(fn): key for key, fn in fetch_map.items()}
            for future, key in futures.items():
                try:
                    result[key] = future.result(timeout=_SERVICE_TIMEOUT + 3)
                except FuturesTimeoutError:
                    _logger.warning("서비스 조회 타임아웃: %s", key)
                except Exception:
                    _logger.warning("서비스 조회 실패: %s", key, exc_info=True)

        return result

    try:
        return await cached_call("union:admin:services", ttl_normal(), _collect_all, refresh=refresh)
    except Exception:
        raise HTTPException(status_code=500, detail="서비스 상태 조회 실패")
