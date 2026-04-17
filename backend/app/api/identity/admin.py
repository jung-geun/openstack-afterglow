import asyncio
import itertools
import logging
from concurrent.futures import ThreadPoolExecutor

import openstack
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn, require_admin
from app.utils.version import read_app_version

_logger = logging.getLogger(__name__)
from app.config import get_settings
from app.models.storage import FileStorageInfo, TopologyData, TopologyInstance
from app.services import k3s_db as k3s_cluster
from app.services import libraries as lib_svc
from app.services import library_builder, manila, neutron, nova
from app.services.cache import cached_call, ttl_fast, ttl_normal, ttl_slow

router = APIRouter()


@router.get("/file-storage", response_model=list[FileStorageInfo], dependencies=[Depends(require_admin)])
async def list_admin_file_storages(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """모든 Union 관련 파일 스토리지 목록 (prebuilt + dynamic)."""
    return manila.list_file_storages(conn)


@router.post("/file-storage/build", status_code=202, dependencies=[Depends(require_admin)])
async def trigger_build(
    library_id: str,
    auto_install: bool = Query(False, description="Cloud-init VM으로 자동 패키지 설치"),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """
    사전 빌드 파일 스토리지 생성 트리거.
    auto_install=true: Cloud-init VM으로 자동 패키지 설치 (빌더 설정 필요)
    auto_install=false: 빈 파일 스토리지 생성만 (수동 설치 필요)
    """
    settings = get_settings()
    try:
        lib = lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"알 수 없는 라이브러리: {library_id}")

    existing = manila.list_file_storages(
        conn,
        metadata_filter={
            "union_type": "prebuilt",
            "union_library": library_id,
        },
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"이미 존재하는 사전 빌드 파일 스토리지: {existing[0].id}")

    if auto_install:
        try:
            result = await library_builder.start_build(conn, library_id)
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    file_storage = manila.create_file_storage(
        conn,
        name=f"union-prebuilt-{library_id}",
        size_gb=20,
        share_network_id=settings.os_manila_share_network_id,
        share_type=settings.os_manila_share_type,
        metadata={
            "union_type": "prebuilt",
            "union_library": library_id,
            "union_version": lib.version,
            "union_status": "building",
        },
    )
    return {"file_storage_id": file_storage.id, "status": "building", "library": library_id}


@router.get("/file-storage/builds", dependencies=[Depends(require_admin)])
async def list_active_builds():
    """현재 진행 중인 자동 빌드 목록 조회."""
    return library_builder.get_active_builds()


# ---------------------------------------------------------------------------
# 관리자 전용 엔드포인트
# ---------------------------------------------------------------------------


def _fetch_hypervisors_raw(conn: openstack.connection.Connection) -> list[dict]:
    """Nova microversion 2.53으로 하이퍼바이저 raw JSON 조회.
    2.88+ 에서 vcpus/memory_mb 등 필드가 deprecated되므로 2.53을 명시적으로 사용."""
    endpoint = conn.compute.get_endpoint()
    resp = conn.session.get(
        f"{endpoint}/os-hypervisors/detail",
        headers={"OpenStack-API-Version": "compute 2.53"},
    )
    return resp.json().get("hypervisors", [])


def _fetch_overview_hypervisors(conn) -> dict:
    """하이퍼바이저 집계 데이터 수집."""
    try:
        data = _fetch_hypervisors_raw(conn)
        return {
            "host_count": len(data) or 1,
            "used_vcpus": sum(h.get("vcpus_used", 0) or 0 for h in data),
            "total_ram_mb": sum(h.get("memory_mb", 0) or 0 for h in data),
            "used_ram_mb": sum(h.get("memory_mb_used", 0) or 0 for h in data),
            "running_vms": sum(h.get("running_vms", 0) or 0 for h in data),
            "total_vcpus": sum(h.get("vcpus", 0) or 0 for h in data),
        }
    except Exception:
        _logger.warning("하이퍼바이저 집계 실패", exc_info=True)
        return {
            "host_count": 0,
            "used_vcpus": 0,
            "total_ram_mb": 0,
            "used_ram_mb": 0,
            "running_vms": 0,
            "total_vcpus": 0,
        }


def _fetch_overview_disk(conn) -> dict:
    """Cinder 디스크 사용량 + 용량 수집."""
    used_disk = 0
    total_disk = 0
    try:
        for v in conn.block_storage.volumes(all_projects=True):
            used_disk += v.size or 0
    except Exception:
        pass
    try:
        bs_endpoint = conn.block_storage.get_endpoint()
        limits_resp = conn.session.get(f"{bs_endpoint}/limits")
        abs_limits = limits_resp.json().get("limits", {}).get("absolute", {})
        total_disk = abs_limits.get("maxTotalVolumeGigabytes", 0)
    except Exception:
        pass
    return {"used_disk": used_disk, "total_disk": total_disk}


def _fetch_overview_placement(conn) -> dict:
    """Placement API에서 물리 코어 수 및 allocation_ratio 수집."""
    physical_vcpus = 0
    allowed_vcpus_total = 0
    try:
        placement_ep = conn.placement.get_endpoint()
        rps_resp = conn.session.get(f"{placement_ep}/resource_providers")
        rps = rps_resp.json().get("resource_providers", [])
        for rp in rps:
            inv_resp = conn.session.get(f"{placement_ep}/resource_providers/{rp['uuid']}/inventories")
            vcpu_inv = inv_resp.json().get("inventories", {}).get("VCPU", {})
            inv_total = vcpu_inv.get("total", 0)
            inv_ratio = vcpu_inv.get("allocation_ratio", 1.0)
            physical_vcpus += inv_total
            allowed_vcpus_total += int(inv_total * inv_ratio)
    except Exception:
        _logger.warning("Placement API CPU 조회 실패", exc_info=True)
    return {"physical_vcpus": physical_vcpus, "allowed_vcpus": allowed_vcpus_total}


def _fetch_overview_servers(conn) -> dict:
    """Nova 서버 목록에서 GPU 인스턴스 수 + 상태별 집계."""
    gpu_instances = 0
    instance_stats = {"total": 0, "active": 0, "shutoff": 0, "error": 0, "other": 0}
    try:
        _ep = conn.compute.get_endpoint()
        _params = {"all_tenants": "1", "limit": "1000"}
        _resp = conn.session.get(
            f"{_ep}/servers/detail",
            params=_params,
            headers={"OpenStack-API-Version": "compute 2.53"},
        )
        for s in _resp.json().get("servers", []):
            flavor = s.get("flavor") or {}
            fname = (flavor.get("original_name") or flavor.get("id") or "").lower()
            if "gpu" in fname:
                gpu_instances += 1
            instance_stats["total"] += 1
            st = (s.get("status") or "").upper()
            if st == "ACTIVE":
                instance_stats["active"] += 1
            elif st == "SHUTOFF":
                instance_stats["shutoff"] += 1
            elif st == "ERROR":
                instance_stats["error"] += 1
            else:
                instance_stats["other"] += 1
    except Exception:
        _logger.warning("서버 집계 실패", exc_info=True)
    return {"gpu_instances": gpu_instances, "instance_stats": instance_stats}


def _fetch_overview_containers(conn) -> int:
    """Zun 컨테이너 수 수집."""
    if not get_settings().service_zun_enabled:
        return 0
    try:
        from app.services.zun import list_containers_admin

        return len(list_containers_admin(conn))
    except Exception:
        return 0


def _fetch_overview_file_storage(conn) -> int:
    """Manila 파일 스토리지 수 수집."""
    if not get_settings().service_manila_enabled:
        return 0
    try:
        return len(manila.list_file_storages(conn, all_tenants=True))
    except Exception:
        return 0


@router.get("/overview", dependencies=[Depends(require_admin)])
async def admin_overview(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """하이퍼바이저 및 전체 리소스 집계."""
    try:

        def _collect():
            with ThreadPoolExecutor(max_workers=6) as executor:
                f_hyp = executor.submit(_fetch_overview_hypervisors, conn)
                f_disk = executor.submit(_fetch_overview_disk, conn)
                f_cpu = executor.submit(_fetch_overview_placement, conn)
                f_srv = executor.submit(_fetch_overview_servers, conn)
                f_ctr = executor.submit(_fetch_overview_containers, conn)
                f_fs = executor.submit(_fetch_overview_file_storage, conn)

            hyp = f_hyp.result(timeout=15)
            disk = f_disk.result(timeout=15)
            cpu = f_cpu.result(timeout=15)
            srv = f_srv.result(timeout=15)
            ctr = f_ctr.result(timeout=15)
            fs = f_fs.result(timeout=15)

            # Placement 실패 시 hypervisor 데이터로 fallback
            physical_vcpus = cpu["physical_vcpus"]
            allowed_vcpus = cpu["allowed_vcpus"]
            if physical_vcpus == 0 and hyp["total_vcpus"] > 0:
                physical_vcpus = hyp["total_vcpus"]
                allowed_vcpus = hyp["total_vcpus"]

            return {
                "hypervisor_count": hyp["host_count"],
                "running_vms": hyp["running_vms"],
                "gpu_instances": srv["gpu_instances"],
                "instance_stats": srv["instance_stats"],
                "vcpus": {"total": physical_vcpus, "allowed": allowed_vcpus, "used": hyp["used_vcpus"]},
                "ram_gb": {"total": round(hyp["total_ram_mb"] / 1024, 1), "used": round(hyp["used_ram_mb"] / 1024, 1)},
                "disk_gb": {"total": disk["total_disk"], "used": disk["used_disk"]},
                "containers_count": ctr,
                "file_storage_count": fs,
            }

        return await cached_call("afterglow:admin:overview", ttl_normal(), _collect, refresh=refresh)
    except Exception:
        _logger.warning("admin overview 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="개요 조회 실패")


@router.get("/monitoring/summary", dependencies=[Depends(require_admin)])
async def get_monitoring_summary(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    """분야별 통합 모니터링 요약 (compute/storage/network/container)."""
    try:

        def _collect():
            result: dict = {}
            # -- Compute --
            hyp_data = _fetch_hypervisors_raw(conn)
            hyp_up = sum(1 for h in hyp_data if h.get("state") == "up")
            result["compute"] = {
                "hypervisors_total": len(hyp_data),
                "hypervisors_up": hyp_up,
                "vcpus_used": sum(h.get("vcpus_used", 0) or 0 for h in hyp_data),
                "vcpus_total": sum(h.get("vcpus", 0) or 0 for h in hyp_data),
                "memory_used_mb": sum(h.get("memory_mb_used", 0) or 0 for h in hyp_data),
                "memory_total_mb": sum(h.get("memory_mb", 0) or 0 for h in hyp_data),
                "running_vms": sum(h.get("running_vms", 0) or 0 for h in hyp_data),
            }
            srv_data = _fetch_overview_servers(conn)
            result["compute"]["instance_stats"] = srv_data.get("instance_stats", {})
            result["compute"]["gpu_instances"] = srv_data.get("gpu_instances", 0)
            # -- Storage (volumes) --
            try:
                _ = conn.compute.get_endpoint().replace("/compute", "")
                vol_ep = conn.block_storage.get_endpoint()
                vol_resp = conn.session.get(
                    f"{vol_ep}/volumes/detail",
                    params={"all_tenants": "1", "limit": "1000"},
                )
                volumes = vol_resp.json().get("volumes", [])
                vol_by_status: dict = {}
                total_gb = 0
                for v in volumes:
                    s = v.get("status", "unknown")
                    vol_by_status[s] = vol_by_status.get(s, 0) + 1
                    total_gb += v.get("size", 0)
                result["storage"] = {
                    "volume_count": len(volumes),
                    "volume_by_status": vol_by_status,
                    "total_gb": total_gb,
                }
            except Exception:
                result["storage"] = {"volume_count": 0, "volume_by_status": {}, "total_gb": 0}
            # file storage
            result["storage"]["file_storage_count"] = _fetch_overview_file_storage(conn)
            # -- Network --
            try:
                nets = list(conn.network.networks())
                routers = list(conn.network.routers())
                fips = list(conn.network.ips())
                ports = list(conn.network.ports())
                fip_active = sum(1 for f in fips if f.status == "ACTIVE")
                router_active = sum(1 for r in routers if r.status == "ACTIVE")
                result["network"] = {
                    "network_count": len(nets),
                    "router_count": len(routers),
                    "router_active": router_active,
                    "floatingip_count": len(fips),
                    "floatingip_active": fip_active,
                    "port_count": len(ports),
                }
            except Exception:
                result["network"] = {
                    "network_count": 0,
                    "router_count": 0,
                    "router_active": 0,
                    "floatingip_count": 0,
                    "floatingip_active": 0,
                    "port_count": 0,
                }
            # -- Containers --
            result["containers"] = {
                "zun_count": _fetch_overview_containers(conn),
                "k3s_count": 0,
            }
            # k3s는 async이므로 별도 처리 불가 — 0으로 유지
            return result

        return await cached_call("afterglow:admin:monitoring", ttl_normal(), _collect, refresh=refresh)
    except Exception:
        _logger.warning("monitoring summary 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="모니터링 요약 조회 실패")


@router.get("/hypervisors", dependencies=[Depends(require_admin)])
async def list_hypervisors(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """컴퓨트 하이퍼바이저 목록."""
    try:

        def _list():
            data = _fetch_hypervisors_raw(conn)
            # Placement API에서 allocation_ratio 수집 (root RP만)
            ratios: dict[str, dict] = {}
            try:
                placement_ep = conn.placement.get_endpoint()
                rps_resp = conn.session.get(f"{placement_ep}/resource_providers")
                for rp in rps_resp.json().get("resource_providers", []):
                    if rp.get("parent_provider_uuid"):  # child RP(GPU 등) 건너뜀
                        continue
                    inv_resp = conn.session.get(f"{placement_ep}/resource_providers/{rp['uuid']}/inventories")
                    invs = inv_resp.json().get("inventories", {})
                    ratios[rp["uuid"]] = {
                        "vcpu": invs.get("VCPU", {}).get("allocation_ratio", 1.0),
                        "memory": invs.get("MEMORY_MB", {}).get("allocation_ratio", 1.0),
                    }
            except Exception:
                _logger.warning("Placement allocation_ratio 조회 실패", exc_info=True)
            return [
                {
                    "id": h.get("id", ""),
                    "name": h.get("hypervisor_hostname", ""),
                    "state": h.get("state", ""),
                    "status": h.get("status", ""),
                    "hypervisor_type": h.get("hypervisor_type", ""),
                    "vcpus": h.get("vcpus", 0) or 0,
                    "vcpus_used": h.get("vcpus_used", 0) or 0,
                    "vcpus_allowed": int((h.get("vcpus", 0) or 0) * ratios.get(h.get("id", ""), {}).get("vcpu", 1.0)),
                    "memory_size_mb": h.get("memory_mb", 0) or 0,
                    "memory_used_mb": h.get("memory_mb_used", 0) or 0,
                    "memory_allowed_mb": int(
                        (h.get("memory_mb", 0) or 0) * ratios.get(h.get("id", ""), {}).get("memory", 1.0)
                    ),
                    "local_disk_gb": h.get("local_gb", 0) or 0,
                    "local_disk_used_gb": h.get("local_gb_used", 0) or 0,
                    "running_vms": h.get("running_vms", 0) or 0,
                }
                for h in data
            ]

        return await cached_call("afterglow:admin:hypervisors", ttl_normal(), _list, refresh=refresh)
    except Exception:
        _logger.warning("hypervisors 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="하이퍼바이저 조회 실패")


@router.get("/hypervisors/{hypervisor_id}", dependencies=[Depends(require_admin)])
async def get_hypervisor_detail(hypervisor_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """하이퍼바이저 상세 정보 + 해당 호스트의 VM 목록."""
    try:

        def _get():
            endpoint = conn.compute.get_endpoint()
            resp = conn.session.get(
                f"{endpoint}/os-hypervisors/{hypervisor_id}",
                headers={"OpenStack-API-Version": "compute 2.53"},
            )
            h = resp.json().get("hypervisor", {})
            hostname = h.get("hypervisor_hostname", "")
            servers = []
            if hostname:
                try:
                    srv_resp = conn.session.get(
                        f"{endpoint}/servers/detail",
                        params={"all_tenants": "1", "host": hostname, "limit": "200"},
                        headers={"OpenStack-API-Version": "compute 2.53"},
                    )
                    for s in srv_resp.json().get("servers", []):
                        servers.append(
                            {
                                "id": s.get("id", ""),
                                "name": s.get("name", ""),
                                "status": s.get("status", ""),
                                "project_id": s.get("tenant_id", "") or s.get("project_id", ""),
                                "flavor": (s.get("flavor") or {}).get("original_name", ""),
                            }
                        )
                except Exception:
                    pass
            svc = h.get("service") or {}
            # uptime 조회
            uptime_str = ""
            host_time_str = ""
            try:
                ut_resp = conn.session.get(
                    f"{endpoint}/os-hypervisors/{hypervisor_id}/uptime",
                    headers={"OpenStack-API-Version": "compute 2.53"},
                )
                ut_data = ut_resp.json().get("hypervisor", {})
                uptime_str = ut_data.get("uptime", "")
                host_time_str = ut_data.get("host_time", "")
            except Exception:
                pass
            # Placement에서 allocation_ratio 조회
            vcpu_ratio = 1.0
            mem_ratio = 1.0
            try:
                placement_ep = conn.placement.get_endpoint()
                inv_resp = conn.session.get(f"{placement_ep}/resource_providers/{hypervisor_id}/inventories")
                invs = inv_resp.json().get("inventories", {})
                vcpu_ratio = invs.get("VCPU", {}).get("allocation_ratio", 1.0)
                mem_ratio = invs.get("MEMORY_MB", {}).get("allocation_ratio", 1.0)
            except Exception:
                pass
            vcpus_total = h.get("vcpus", 0) or 0
            mem_total = h.get("memory_mb", 0) or 0
            return {
                "id": h.get("id", ""),
                "hypervisor_hostname": hostname,
                "state": h.get("state", ""),
                "status": h.get("status", ""),
                "hypervisor_type": h.get("hypervisor_type", ""),
                "hypervisor_version": h.get("hypervisor_version", 0),
                "host_ip": h.get("host_ip", ""),
                "host_time": host_time_str,
                "uptime": uptime_str,
                "service_host": svc.get("host", ""),
                "vcpus": vcpus_total,
                "vcpus_used": h.get("vcpus_used", 0) or 0,
                "vcpus_allowed": int(vcpus_total * vcpu_ratio),
                "memory_mb": mem_total,
                "memory_mb_used": h.get("memory_mb_used", 0) or 0,
                "memory_allowed_mb": int(mem_total * mem_ratio),
                "local_gb": h.get("local_gb", 0) or 0,
                "local_gb_used": h.get("local_gb_used", 0) or 0,
                "running_vms": h.get("running_vms", 0) or 0,
                "cpu_info": h.get("cpu_info"),
                "servers": servers,
            }

        return await asyncio.to_thread(_get)
    except Exception:
        _logger.warning("하이퍼바이저 상세 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="하이퍼바이저 상세 조회 실패")


@router.get("/all-instances", dependencies=[Depends(require_admin)])
async def list_all_instances(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    host: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 프로젝트의 인스턴스 목록 (페이지네이션)."""
    try:

        def _list():
            endpoint = conn.compute.get_endpoint()
            params: dict = {"all_tenants": "1", "limit": str(limit)}
            if marker:
                params["marker"] = marker
            if project_id:
                params["tenant_id"] = project_id
            if host:
                params["host"] = host
            resp = conn.session.get(
                f"{endpoint}/servers/detail",
                params=params,
                headers={"OpenStack-API-Version": "compute 2.53"},
            )
            servers = resp.json().get("servers", [])
            items = []
            for s in servers[:limit]:
                fault_info = None
                if (s.get("status") or "").upper() == "ERROR":
                    fault = s.get("fault") or {}
                    if isinstance(fault, dict) and fault.get("message"):
                        fault_info = fault.get("message", "")
                server_host = s.get("OS-EXT-SRV-ATTR:host") or s.get("host")
                flavor = s.get("flavor") or {}
                items.append(
                    {
                        "id": s.get("id", ""),
                        "name": s.get("name") or "",
                        "status": s.get("status") or "",
                        "project_id": s.get("tenant_id") or s.get("project_id"),
                        "user_id": s.get("user_id"),
                        "flavor": flavor.get("original_name") or flavor.get("id") or "",
                        "host": server_host,
                        "created_at": s.get("created"),
                        "fault": fault_info,
                    }
                )
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}

        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="전체 인스턴스 조회 실패")


@router.get("/all-volumes", dependencies=[Depends(require_admin)])
async def list_all_volumes(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 프로젝트의 볼륨 목록 (페이지네이션)."""
    try:

        def _list():
            kwargs: dict = {"details": True, "all_projects": True, "limit": limit}
            if marker:
                kwargs["marker"] = marker
            items = [
                {
                    "id": v.id,
                    "name": v.name or "",
                    "status": v.status or "",
                    "size": v.size,
                    "project_id": getattr(v, "project_id", None),
                    "created_at": str(v.created_at) if getattr(v, "created_at", None) else None,
                }
                for v in itertools.islice(conn.block_storage.volumes(**kwargs), limit)
            ]
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}

        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="전체 볼륨 조회 실패")


@router.get("/all-containers", dependencies=[Depends(require_admin)])
async def list_all_containers(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    """전체 프로젝트의 컨테이너 목록 (Zun)."""
    if not get_settings().service_zun_enabled:
        return []
    from app.services.zun import ZunServiceUnavailable, list_containers_admin

    try:
        return await cached_call(
            "afterglow:admin:containers", ttl_normal(), lambda: list_containers_admin(conn), refresh=refresh
        )
    except ZunServiceUnavailable:
        return []
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 조회 실패")


@router.get("/containers/{container_id}", dependencies=[Depends(require_admin)])
async def get_admin_container(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 컨테이너 단건 조회."""
    if not get_settings().service_zun_enabled:
        raise HTTPException(status_code=503, detail="Zun 서비스가 비활성화되어 있습니다")
    from app.services.zun import ZunServiceUnavailable, get_container

    try:
        return await asyncio.to_thread(get_container, conn, container_id)
    except ZunServiceUnavailable:
        raise HTTPException(status_code=503, detail="컨테이너 서비스를 사용할 수 없습니다")
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.get("/containers/{container_id}/logs", dependencies=[Depends(require_admin)])
async def get_admin_container_logs(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 컨테이너 로그 조회."""
    if not get_settings().service_zun_enabled:
        raise HTTPException(status_code=503, detail="Zun 서비스가 비활성화되어 있습니다")
    from app.services.zun import ZunServiceUnavailable, get_container_logs

    try:
        logs = await asyncio.to_thread(get_container_logs, conn, container_id)
        return {"logs": logs}
    except ZunServiceUnavailable:
        raise HTTPException(status_code=503, detail="컨테이너 서비스를 사용할 수 없습니다")
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.post("/containers/{container_id}/start", dependencies=[Depends(require_admin)])
async def start_admin_container(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 컨테이너 시작."""
    if not get_settings().service_zun_enabled:
        raise HTTPException(status_code=503, detail="Zun 서비스가 비활성화되어 있습니다")
    from app.services import zun as _zun

    try:
        await asyncio.to_thread(_zun.start_container, conn, container_id)
        return {"status": "started"}
    except Exception:
        _logger.warning("컨테이너 시작 실패: %s", container_id, exc_info=True)
        raise HTTPException(status_code=500, detail="컨테이너 시작 실패")


@router.post("/containers/{container_id}/stop", dependencies=[Depends(require_admin)])
async def stop_admin_container(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 컨테이너 중지."""
    if not get_settings().service_zun_enabled:
        raise HTTPException(status_code=503, detail="Zun 서비스가 비활성화되어 있습니다")
    from app.services import zun as _zun

    try:
        await asyncio.to_thread(_zun.stop_container, conn, container_id)
        return {"status": "stopped"}
    except Exception:
        _logger.warning("컨테이너 중지 실패: %s", container_id, exc_info=True)
        raise HTTPException(status_code=500, detail="컨테이너 중지 실패")


@router.delete("/containers/{container_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_admin_container(
    container_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 컨테이너 삭제."""
    if not get_settings().service_zun_enabled:
        raise HTTPException(status_code=503, detail="Zun 서비스가 비활성화되어 있습니다")
    from app.services import zun as _zun

    try:
        await asyncio.to_thread(_zun.delete_container, conn, container_id)
    except Exception:
        _logger.warning("컨테이너 삭제 실패: %s", container_id, exc_info=True)
        raise HTTPException(status_code=500, detail="컨테이너 삭제 실패")


@router.get("/all-file-storages", dependencies=[Depends(require_admin)])
async def list_all_file_storages(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    """전체 프로젝트의 파일 스토리지 목록 (Manila)."""
    if not get_settings().service_manila_enabled:
        return []
    try:
        return await cached_call(
            "afterglow:admin:file_storages",
            ttl_normal(),
            lambda: manila.list_file_storages(conn, None, True),
            refresh=refresh,
        )
    except Exception:
        raise HTTPException(status_code=500, detail="파일 스토리지 조회 실패")


@router.get("/topology", response_model=TopologyData, dependencies=[Depends(require_admin)])
async def admin_topology(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """전체 프로젝트의 네트워크/라우터/인스턴스 토폴로지."""

    def _fetch():
        topo = neutron.get_topology(conn)
        instances = []
        for s in conn.compute.servers(details=True, all_projects=True):
            addresses = getattr(s, "addresses", {}) or {}
            instances.append(
                TopologyInstance(
                    id=s.id,
                    name=s.name or "",
                    status=s.status or "",
                    network_names=list(set(addresses.keys())),
                    ip_addresses=[
                        {"addr": addr["addr"], "type": addr.get("OS-EXT-IPS:type", ""), "network_name": net_name}
                        for net_name, addrs in addresses.items()
                        for addr in addrs
                    ],
                )
            )
        topo.instances = instances
        return topo.model_dump()

    try:
        return await cached_call("afterglow:admin:topology", ttl_normal(), _fetch, refresh=refresh)
    except Exception:
        _logger.exception("토폴로지 조회 실패")
        raise HTTPException(status_code=500, detail="토폴로지 조회 실패")


@router.get("/timeseries/{resource_type}", dependencies=[Depends(require_admin)])
async def get_timeseries(
    resource_type: str,
    range: str = Query(default="7d", pattern="^(1d|2d|7d|30d)$"),
):
    """리소스 유형별 시계열 스냅샷 반환."""
    from app.services import timeseries

    valid = {"instances", "volumes", "file_storage", "networks"}
    if resource_type not in valid:
        raise HTTPException(status_code=400, detail=f"resource_type은 {valid} 중 하나여야 합니다")
    return await timeseries.get_timeseries(resource_type, range)


@router.get("/all-networks", dependencies=[Depends(require_admin)])
async def list_all_networks(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """전체 프로젝트의 네트워크 목록."""
    try:
        return await cached_call(
            "afterglow:admin:networks", ttl_normal(), lambda: neutron.list_networks(conn, None), refresh=refresh
        )
    except Exception:
        raise HTTPException(status_code=500, detail="네트워크 목록 조회 실패")


@router.get("/all-floating-ips", dependencies=[Depends(require_admin)])
async def list_all_floating_ips(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    """전체 프로젝트의 Floating IP 목록."""
    try:
        return await cached_call(
            "afterglow:admin:floating_ips", ttl_fast(), lambda: neutron.list_floating_ips(conn, None), refresh=refresh
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Floating IP 목록 조회 실패")


@router.get("/all-routers", dependencies=[Depends(require_admin)])
async def list_all_routers(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """전체 프로젝트의 라우터 목록."""
    try:
        return await cached_call(
            "afterglow:admin:routers", ttl_normal(), lambda: neutron.list_routers(conn, None), refresh=refresh
        )
    except Exception:
        raise HTTPException(status_code=500, detail="라우터 목록 조회 실패")


@router.get("/all-ports", dependencies=[Depends(require_admin)])
async def list_all_ports(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    """전체 프로젝트의 포트 목록 (페이지네이션)."""
    try:

        def _list():
            kwargs: dict = {"limit": limit}
            if marker:
                kwargs["marker"] = marker
            if project_id:
                kwargs["project_id"] = project_id
            items = []
            for p in conn.network.ports(**kwargs):
                items.append(
                    {
                        "id": p.id,
                        "name": p.name or "",
                        "status": p.status or "",
                        "network_id": p.network_id,
                        "device_owner": p.device_owner or "",
                        "device_id": p.device_id or "",
                        "mac_address": p.mac_address or "",
                        "fixed_ips": p.fixed_ips or [],
                        "project_id": getattr(p, "project_id", None),
                    }
                )
                if len(items) >= limit:
                    break
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}

        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="포트 목록 조회 실패")


class CreatePortRequest(BaseModel):
    network_id: str
    name: str = ""
    project_id: str | None = None
    fixed_ip: str | None = None


@router.post("/ports", dependencies=[Depends(require_admin)], status_code=201)
async def create_port(
    req: CreatePortRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """포트 생성 (관리자)."""
    try:

        def _create():
            kwargs: dict = {"network_id": req.network_id}
            if req.name:
                kwargs["name"] = req.name
            if req.project_id:
                kwargs["project_id"] = req.project_id
            if req.fixed_ip:
                kwargs["fixed_ips"] = [{"ip_address": req.fixed_ip}]
            p = conn.network.create_port(**kwargs)
            return {
                "id": p.id,
                "name": p.name or "",
                "status": p.status or "",
                "network_id": p.network_id,
                "device_owner": p.device_owner or "",
                "device_id": p.device_id or "",
                "mac_address": p.mac_address or "",
                "fixed_ips": p.fixed_ips or [],
                "project_id": getattr(p, "project_id", None),
            }

        return await asyncio.to_thread(_create)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"포트 생성 실패: {e}")


@router.get("/quotas/{project_id}", dependencies=[Depends(require_admin)])
async def get_quotas(project_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """특정 프로젝트의 쿼터 조회 (Compute + Volume, 실제 사용량 포함)."""
    try:

        def _get():
            result: dict = {"compute": {}, "volume": {}}
            compute_endpoint = conn.compute.get_endpoint()
            bs_endpoint = conn.block_storage.get_endpoint()
            try:
                cq = conn.session.get(f"{compute_endpoint}/os-quota-sets/{project_id}/detail")
                qs = cq.json().get("quota_set", {})
                for key in ("instances", "cores", "ram"):
                    q = qs.get(key, {})
                    result["compute"][key] = {"limit": q.get("limit", 0), "in_use": q.get("in_use", 0)}
            except Exception:
                result["compute"] = {}
            try:
                bq = conn.session.get(f"{bs_endpoint}/os-quota-sets/{project_id}", params={"usage": "true"})
                bqs = bq.json().get("quota_set", {})
                for key in ("volumes", "gigabytes"):
                    q = bqs.get(key, {})
                    if isinstance(q, dict):
                        result["volume"][key] = {"limit": q.get("limit", 0), "in_use": q.get("in_use", 0)}
                    else:
                        result["volume"][key] = {"limit": q, "in_use": 0}
            except Exception:
                result["volume"] = {}
            return result

        return await asyncio.to_thread(_get)
    except Exception:
        raise HTTPException(status_code=500, detail="쿼터 조회 실패")


@router.get("/overview/projects", dependencies=[Depends(require_admin)])
async def admin_overview_projects(
    conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)
):
    """프로젝트별 리소스 사용량 및 쿼터."""
    try:

        def _collect():
            # 프로젝트별 GPU 인스턴스 수 집계
            gpu_by_project: dict = {}
            try:
                endpoint = conn.compute.get_endpoint()
                params = {"all_tenants": "1", "limit": "1000"}
                resp = conn.session.get(
                    f"{endpoint}/servers/detail",
                    params=params,
                    headers={"OpenStack-API-Version": "compute 2.53"},
                )
                for s in resp.json().get("servers", []):
                    pid = s.get("tenant_id") or s.get("project_id") or ""
                    fname = (s.get("flavor") or {}).get("original_name") or ""
                    if "gpu" in fname.lower():
                        gpu_by_project[pid] = gpu_by_project.get(pid, 0) + 1
            except Exception:
                pass

            compute_endpoint = conn.compute.get_endpoint()
            bs_endpoint = conn.block_storage.get_endpoint()
            projects = list(conn.identity.projects())

            def _fetch_project_quota(p) -> dict:
                pid = p.id
                row: dict = {
                    "project_id": pid,
                    "project_name": p.name or "",
                    "cpu": {"used": 0, "quota": -1},
                    "ram_mb": {"used": 0, "quota": -1},
                    "instances": {"used": 0, "quota": -1},
                    "disk_gb": {"used": 0, "quota": -1},
                    "gpu_instances": gpu_by_project.get(pid, 0),
                }
                try:
                    cq_resp = conn.session.get(f"{compute_endpoint}/os-quota-sets/{pid}/detail")
                    qs = cq_resp.json().get("quota_set", {})
                    cores = qs.get("cores", {})
                    ram = qs.get("ram", {})
                    instances = qs.get("instances", {})
                    row["cpu"] = {"used": cores.get("in_use", 0), "quota": cores.get("limit", -1)}
                    row["ram_mb"] = {"used": ram.get("in_use", 0), "quota": ram.get("limit", -1)}
                    row["instances"] = {"used": instances.get("in_use", 0), "quota": instances.get("limit", -1)}
                except Exception:
                    pass
                try:
                    bq_resp = conn.session.get(f"{bs_endpoint}/os-quota-sets/{pid}", params={"usage": "true"})
                    bqs = bq_resp.json().get("quota_set", {})
                    gb = bqs.get("gigabytes", {})
                    gb_used = gb.get("in_use", 0) if isinstance(gb, dict) else 0
                    gb_limit = gb.get("limit", -1) if isinstance(gb, dict) else -1
                    row["disk_gb"] = {"used": gb_used, "quota": gb_limit}
                except Exception:
                    pass
                return row

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(_fetch_project_quota, p) for p in projects]
            result = []
            for f in futures:
                try:
                    result.append(f.result(timeout=15))
                except Exception:
                    pass
            return result

        return await cached_call("afterglow:admin:overview_projects", ttl_slow(), _collect, refresh=refresh)
    except Exception:
        _logger.warning("프로젝트별 리소스 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="프로젝트별 리소스 조회 실패")


# ===========================================================================
# 볼륨 관리 (관리자)
# ===========================================================================


@router.get("/volumes/{volume_id}", dependencies=[Depends(require_admin)])
async def get_admin_volume(volume_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """볼륨 상세 조회 (관리자)."""
    try:

        def _get():
            v = conn.block_storage.get_volume(volume_id)
            return {
                "id": v.id,
                "name": v.name or "",
                "status": v.status or "",
                "size": v.size or 0,
                "volume_type": v.volume_type or "",
                "project_id": getattr(v, "project_id", None) or getattr(v, "os-vol-tenant-attr:tenant_id", None),
                "attachments": [dict(a) for a in (v.attachments or [])],
                "created_at": str(v.created_at) if v.created_at else None,
                "description": v.description or "",
                "bootable": getattr(v, "is_bootable", None),
                "encrypted": getattr(v, "is_encrypted", None),
                "multiattach": getattr(v, "is_multiattach", None),
                "metadata": dict(v.metadata or {}),
            }

        return await asyncio.to_thread(_get)
    except Exception:
        _logger.warning("볼륨 상세 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="볼륨 상세 조회 실패")


class UpdateVolumeRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ExtendVolumeRequest(BaseModel):
    new_size: int  # GB


class ResetVolumeStatusRequest(BaseModel):
    status: str = "available"


@router.patch("/volumes/{volume_id}", dependencies=[Depends(require_admin)])
async def update_volume(
    volume_id: str,
    req: UpdateVolumeRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 이름/설명 수정."""

    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.description is not None:
            kwargs["description"] = req.description
        try:
            v = conn.block_storage.update_volume(volume_id, **kwargs)
            return {
                "id": v.id,
                "name": v.name or "",
                "status": v.status or "",
                "size": v.size,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"볼륨 수정 실패: {e}")

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.delete("/volumes/{volume_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_volume(
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 삭제."""

    def _delete():
        try:
            conn.block_storage.delete_volume(volume_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"볼륨 삭제 실패: {e}")

    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.post("/volumes/{volume_id}/extend", dependencies=[Depends(require_admin)])
async def extend_volume(
    volume_id: str,
    req: ExtendVolumeRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 용량 확장."""

    def _extend():
        try:
            conn.block_storage.extend_volume(volume_id, req.new_size)
            return {"status": "extending"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"볼륨 확장 실패: {e}")

    try:
        return await asyncio.to_thread(_extend)
    except HTTPException:
        raise


@router.post("/volumes/{volume_id}/reset-status", dependencies=[Depends(require_admin)])
async def reset_volume_status(
    volume_id: str,
    req: ResetVolumeStatusRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨 상태 초기화."""

    def _reset():
        try:
            conn.block_storage.reset_volume_status(volume_id, req.status)
            return {"status": req.status}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"볼륨 상태 초기화 실패: {e}")

    try:
        return await asyncio.to_thread(_reset)
    except HTTPException:
        raise


class LiveMigrateRequest(BaseModel):
    host: str | None = None
    block_migration: str = "auto"


class ColdMigrateRequest(BaseModel):
    pass


@router.get("/compute-hosts", dependencies=[Depends(require_admin)])
async def list_compute_hosts(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """마이그레이션 가능한 컴퓨트 호스트 목록."""
    try:
        return await asyncio.to_thread(nova.list_compute_hosts, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="컴퓨트 호스트 목록 조회 실패")


@router.post("/instances/{server_id}/live-migrate", dependencies=[Depends(require_admin)])
async def live_migrate_instance(
    server_id: str,
    req: LiveMigrateRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 라이브 마이그레이션."""
    try:
        await asyncio.to_thread(nova.live_migrate_server, conn, server_id, req.host, req.block_migration)
        return {"status": "migrating"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"라이브 마이그레이션 실패: {e}")


@router.post("/instances/{server_id}/cold-migrate", dependencies=[Depends(require_admin)])
async def cold_migrate_instance(
    server_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """인스턴스 콜드 마이그레이션."""
    try:
        await asyncio.to_thread(nova.cold_migrate_server, conn, server_id)
        return {"status": "migrating"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"콜드 마이그레이션 실패: {e}")


@router.post("/instances/{server_id}/confirm-resize", dependencies=[Depends(require_admin)])
async def confirm_resize_instance(
    server_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """콜드 마이그레이션 후 리사이즈 확인."""
    try:
        await asyncio.to_thread(nova.confirm_resize_server, conn, server_id)
        return {"status": "confirmed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"리사이즈 확인 실패: {e}")


class VolumeTransferRequest(BaseModel):
    target_project_id: str


@router.post("/volumes/{volume_id}/transfer", dependencies=[Depends(require_admin)])
async def transfer_volume(
    volume_id: str,
    req: VolumeTransferRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """볼륨을 다른 프로젝트로 이전 (관리자 전용)."""
    try:

        def _transfer():
            bs_endpoint = conn.block_storage.get_endpoint()
            # 1. 이전 생성
            create_resp = conn.session.post(
                f"{bs_endpoint}/os-volume-transfer",
                json={"transfer": {"name": f"admin-transfer-{volume_id[:8]}", "volume_id": volume_id}},
            )
            transfer = create_resp.json().get("transfer", {})
            transfer_id = transfer.get("id")
            auth_key = transfer.get("auth_key")
            if not transfer_id or not auth_key:
                raise Exception("이전 생성 실패: transfer_id 또는 auth_key를 받지 못했습니다")
            # 2. 대상 프로젝트 범위로 이전 수락
            accept_resp = conn.session.post(
                f"{bs_endpoint}/os-volume-transfer/{transfer_id}/accept",
                json={"accept": {"auth_key": auth_key}},
                endpoint_override=None,
                headers={"X-Project-Id": req.target_project_id},
            )
            result = accept_resp.json().get("transfer", {})
            return {"status": "transferred", "volume_id": result.get("volume_id", volume_id)}

        return await asyncio.to_thread(_transfer)
    except Exception as e:
        _logger.warning("볼륨 이전 실패", exc_info=True)
        raise HTTPException(status_code=400, detail=f"볼륨 이전 실패: {e}")


# ===========================================================================
# 네트워크 관리 (관리자)
# ===========================================================================


class CreateNetworkRequest(BaseModel):
    name: str
    is_external: bool = False
    is_shared: bool = False
    cidr: str | None = None
    enable_dhcp: bool = True


class UpdateNetworkRequest(BaseModel):
    name: str | None = None
    is_shared: bool | None = None


class CreateRouterRequest(BaseModel):
    name: str
    external_network_id: str | None = None


class UpdateRouterRequest(BaseModel):
    name: str | None = None
    external_network_id: str | None = None


class CreateFloatingIpRequest(BaseModel):
    floating_network_id: str


class UpdatePortRequest(BaseModel):
    name: str | None = None


@router.get("/networks/{network_id}", dependencies=[Depends(require_admin)])
async def get_admin_network(network_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """네트워크 상세 조회 (관리자)."""
    try:
        return await asyncio.to_thread(neutron.get_network_detail, conn, network_id)
    except Exception:
        raise HTTPException(status_code=404, detail="네트워크를 찾을 수 없습니다")


@router.post("/networks", dependencies=[Depends(require_admin)], status_code=201)
async def create_network(
    req: CreateNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """네트워크 생성 (선택적으로 서브넷 포함)."""

    def _create():
        try:
            net_kwargs: dict = {
                "name": req.name,
                "is_router_external": req.is_external,
                "is_shared": req.is_shared,
            }
            n = conn.network.create_network(**net_kwargs)
            if req.cidr:
                conn.network.create_subnet(
                    network_id=n.id,
                    name=f"{req.name}-subnet",
                    cidr=req.cidr,
                    ip_version=4,
                    is_dhcp_enabled=req.enable_dhcp,
                )
            return {
                "id": n.id,
                "name": n.name or "",
                "status": n.status or "",
                "is_external": bool(n.is_router_external),
                "is_shared": bool(n.is_shared),
                "subnets": n.subnet_ids or [],
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"네트워크 생성 실패: {e}")

    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.put("/networks/{network_id}", dependencies=[Depends(require_admin)])
async def update_network(
    network_id: str,
    req: UpdateNetworkRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """네트워크 수정."""

    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.is_shared is not None:
            kwargs["is_shared"] = req.is_shared
        try:
            n = conn.network.update_network(network_id, **kwargs)
            return {
                "id": n.id,
                "name": n.name or "",
                "status": n.status or "",
                "is_external": bool(n.is_router_external),
                "is_shared": bool(n.is_shared),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"네트워크 수정 실패: {e}")

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.delete("/networks/{network_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_network(
    network_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """네트워크 삭제."""

    def _delete():
        try:
            conn.network.delete_network(network_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"네트워크 삭제 실패: {e}")

    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.post("/floating-ips", dependencies=[Depends(require_admin)], status_code=201)
async def create_floating_ip(
    req: CreateFloatingIpRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Floating IP 생성."""

    def _create():
        try:
            fip = conn.network.create_ip(floating_network_id=req.floating_network_id)
            return {
                "id": fip.id,
                "floating_ip_address": fip.floating_ip_address or "",
                "fixed_ip_address": fip.fixed_ip_address,
                "status": fip.status or "",
                "port_id": fip.port_id,
                "project_id": getattr(fip, "project_id", None),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Floating IP 생성 실패: {e}")

    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.delete("/floating-ips/{fip_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_floating_ip(
    fip_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Floating IP 삭제."""

    def _delete():
        try:
            conn.network.delete_ip(fip_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Floating IP 삭제 실패: {e}")

    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.post("/routers", dependencies=[Depends(require_admin)], status_code=201)
async def create_router(
    req: CreateRouterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """라우터 생성."""

    def _create():
        try:
            kwargs: dict = {"name": req.name}
            if req.external_network_id:
                kwargs["external_gateway_info"] = {"network_id": req.external_network_id}
            r = conn.network.create_router(**kwargs)
            return {
                "id": r.id,
                "name": r.name or "",
                "status": r.status or "",
                "external_gateway_network_id": (r.external_gateway_info or {}).get("network_id"),
                "project_id": getattr(r, "project_id", None),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"라우터 생성 실패: {e}")

    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.put("/routers/{router_id}", dependencies=[Depends(require_admin)])
async def update_router(
    router_id: str,
    req: UpdateRouterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """라우터 수정."""

    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.external_network_id is not None:
            kwargs["external_gateway_info"] = {"network_id": req.external_network_id} if req.external_network_id else {}
        try:
            r = conn.network.update_router(router_id, **kwargs)
            return {
                "id": r.id,
                "name": r.name or "",
                "status": r.status or "",
                "external_gateway_network_id": (r.external_gateway_info or {}).get("network_id"),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"라우터 수정 실패: {e}")

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.delete("/routers/{router_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_router(
    router_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """라우터 삭제."""

    def _delete():
        try:
            conn.network.delete_router(router_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"라우터 삭제 실패: {e}")

    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.put("/ports/{port_id}", dependencies=[Depends(require_admin)])
async def update_port(
    port_id: str,
    req: UpdatePortRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """포트 수정 (이름)."""

    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        try:
            p = conn.network.update_port(port_id, **kwargs)
            return {
                "id": p.id,
                "name": p.name or "",
                "status": p.status or "",
                "device_owner": p.device_owner or "",
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"포트 수정 실패: {e}")

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.delete("/ports/{port_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_port(
    port_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """포트 삭제."""

    def _delete():
        try:
            conn.network.delete_port(port_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"포트 삭제 실패: {e}")

    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


# ===========================================================================
# k3s 클러스터 관리 (관리자)
# ===========================================================================


@router.get("/k3s-clusters", dependencies=[Depends(require_admin)])
async def list_admin_k3s_clusters():
    """전체 프로젝트의 k3s 클러스터 목록 (관리자용)."""
    try:
        clusters = await k3s_cluster.list_all_clusters()
        return clusters
    except Exception:
        _logger.warning("k3s 클러스터 목록 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="k3s 클러스터 목록 조회 실패")


@router.get("/k3s-clusters/{cluster_id}", dependencies=[Depends(require_admin)])
async def get_admin_k3s_cluster(cluster_id: str):
    """관리자용 단일 k3s 클러스터 조회 (프로젝트 필터 없음)."""
    cluster = await k3s_cluster.get_cluster_admin(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    return cluster


@router.get("/k3s-clusters/{cluster_id}/kubeconfig", dependencies=[Depends(require_admin)])
async def download_admin_k3s_kubeconfig(cluster_id: str):
    """관리자용 kubeconfig 다운로드."""
    from fastapi.responses import Response

    cluster = await k3s_cluster.get_cluster_admin(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    try:
        kubeconfig = await k3s_cluster.get_kubeconfig_admin(cluster_id)
    except Exception as e:
        _logger.error("admin kubeconfig 복호화 실패: %s", e)
        raise HTTPException(status_code=500, detail="kubeconfig 복호화에 실패했습니다. 관리자에게 문의하세요.")
    if not kubeconfig:
        raise HTTPException(status_code=404, detail="kubeconfig가 아직 준비되지 않았습니다.")

    cluster_name = cluster.get("name", cluster_id)
    return Response(
        content=kubeconfig,
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="kubeconfig-{cluster_name}.yaml"'},
    )


@router.patch("/k3s-clusters/{cluster_id}/scale", dependencies=[Depends(require_admin)])
async def scale_admin_k3s_cluster(cluster_id: str, req: dict):
    """관리자용 k3s 클러스터 에이전트 스케일링."""
    import asyncio

    from app.api.k3s.clusters import _scale_agents

    cluster = await k3s_cluster.get_cluster_admin(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    if cluster.get("status") != "ACTIVE":
        raise HTTPException(status_code=409, detail="ACTIVE 상태의 클러스터만 스케일링할 수 있습니다")

    desired = req.get("agent_count")
    if desired is None or not isinstance(desired, int) or desired < 0:
        raise HTTPException(status_code=422, detail="agent_count는 0 이상의 정수여야 합니다")

    project_id = cluster.get("project_id", "")
    current_agent_ids: list[str] = cluster.get("agent_vm_ids") or []
    if isinstance(current_agent_ids, str):
        import json as _json

        try:
            current_agent_ids = _json.loads(current_agent_ids)
        except Exception:
            current_agent_ids = []

    if desired == len(current_agent_ids):
        return {"message": "변경 없음", "agent_count": desired}

    await k3s_cluster.update_cluster_status(project_id, cluster_id, "SCALING")
    asyncio.create_task(_scale_agents(project_id, cluster_id, current_agent_ids, desired))
    return {"message": f"스케일링 시작: {len(current_agent_ids)} → {desired}", "agent_count": desired}


@router.delete("/k3s-clusters/{cluster_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_admin_k3s_cluster(
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """관리자용 k3s 클러스터 삭제."""
    import asyncio

    from app.services import neutron as _neutron
    from app.services import nova as _nova

    cluster = await k3s_cluster.get_cluster_admin(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    project_id = cluster.get("project_id", "")
    await k3s_cluster.update_cluster_status(project_id, cluster_id, "DELETING")

    # 에이전트 VM 병렬 삭제
    agent_vm_ids = cluster.get("agent_vm_ids") or []
    if isinstance(agent_vm_ids, str):
        import json

        try:
            agent_vm_ids = json.loads(agent_vm_ids)
        except Exception:
            agent_vm_ids = []

    async def _del_vm(vm_id: str) -> None:
        try:
            await asyncio.to_thread(_nova.delete_server, conn, vm_id)
        except Exception as e:
            _logger.warning("Delete agent VM %s failed: %s", vm_id, e)

    await asyncio.gather(*[_del_vm(vid) for vid in agent_vm_ids], return_exceptions=True)

    server_vm_id = cluster.get("server_vm_id")
    if server_vm_id:
        try:
            await asyncio.to_thread(_nova.delete_server, conn, server_vm_id)
        except Exception as e:
            _logger.warning("Delete server VM %s failed: %s", server_vm_id, e)

    sg_id = cluster.get("security_group_id")
    if sg_id:
        try:
            await asyncio.sleep(3)
            await asyncio.to_thread(_neutron.delete_security_group, conn, sg_id)
        except Exception as e:
            _logger.warning("Delete SG %s failed: %s", sg_id, e)

    await k3s_cluster.delete_cluster_record(project_id, cluster_id)


# ===========================================================================
# 시스템 버전 정보
# ===========================================================================

_admin_start_time: float = __import__("time").time()


_backend_version: str = read_app_version()


@router.get("/version", dependencies=[Depends(require_admin)])
async def admin_version():
    """플랫폼 버전, 런타임, 의존성, Git 정보 반환."""
    import importlib.metadata
    import platform
    import subprocess
    import time

    s = get_settings()

    # 의존성 버전
    deps: dict = {}
    for pkg in ("fastapi", "openstacksdk", "python-keystoneclient", "pydantic", "uvicorn"):
        try:
            deps[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            deps[pkg] = None

    # Git 정보 (Docker 환경에서는 없을 수 있음)
    def _git(args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                timeout=3,
                cwd="/app",
            )
            return result.stdout.strip() or None
        except Exception:
            return None

    git_commit = _git(["rev-parse", "--short", "HEAD"])
    git_tag = _git(["describe", "--tags", "--abbrev=0"])
    git_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])

    return {
        "platform": {
            "backend_version": _backend_version,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "uptime_seconds": int(time.time() - _admin_start_time),
        },
        "dependencies": deps,
        "git": {
            "commit": git_commit,
            "tag": git_tag,
            "branch": git_branch,
        },
        "config": {
            "k3s_version": s.k3s_version,
        },
    }
