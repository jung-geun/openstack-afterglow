import asyncio
import itertools
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn, get_token_info, require_admin

_logger = logging.getLogger(__name__)
from app.models.storage import ShareInfo, TopologyData, TopologyInstance
from app.services import manila, libraries as lib_svc, neutron
from app.services.cache import cached_call
from app.config import get_settings

router = APIRouter()


@router.get("/shares", response_model=list[ShareInfo], dependencies=[Depends(require_admin)])
async def list_admin_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """모든 Union 관련 share 목록 (prebuilt + dynamic)."""
    return manila.list_shares(conn)


@router.post("/shares/build", status_code=202, dependencies=[Depends(require_admin)])
async def trigger_build(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """
    사전 빌드 share 생성 트리거.
    실제 빌드는 별도 백그라운드 프로세스(scripts/build_library_shares.py)에서 수행.
    여기서는 빈 share를 생성하고 메타데이터만 기록한다.
    """
    settings = get_settings()
    try:
        lib = lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"알 수 없는 라이브러리: {library_id}")

    existing = manila.list_shares(conn, metadata_filter={
        "union_type": "prebuilt",
        "union_library": library_id,
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"이미 존재하는 사전 빌드 share: {existing[0].id}"
        )

    share = manila.create_share(
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
    return {"share_id": share.id, "status": "building", "library": library_id}


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


@router.get("/overview", dependencies=[Depends(require_admin)])
async def admin_overview(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """하이퍼바이저 및 전체 리소스 집계."""
    try:
        def _collect():
            data = _fetch_hypervisors_raw(conn)
            host_count = len(data) or 1
            used_vcpus = sum(h.get("vcpus_used", 0) or 0 for h in data)
            total_ram = sum(h.get("memory_mb", 0) or 0 for h in data)
            used_ram = sum(h.get("memory_mb_used", 0) or 0 for h in data)
            # Ceph: 모든 hypervisor가 동일한 pool 용량을 보고하므로 host 수로 나눔
            total_disk = sum(h.get("local_gb", 0) or 0 for h in data) // host_count
            used_disk = sum(h.get("local_gb_used", 0) or 0 for h in data) // host_count
            running_vms = sum(h.get("running_vms", 0) or 0 for h in data)

            # CPU: Placement API에서 물리 코어 수 및 allocation_ratio 조회
            physical_vcpus = 0
            allowed_vcpus_total = 0
            try:
                placement_ep = conn.placement.get_endpoint()
                rps_resp = conn.session.get(f"{placement_ep}/resource_providers")
                rps = rps_resp.json().get("resource_providers", [])
                for rp in rps:
                    inv_resp = conn.session.get(
                        f"{placement_ep}/resource_providers/{rp['uuid']}/inventories"
                    )
                    vcpu_inv = inv_resp.json().get("inventories", {}).get("VCPU", {})
                    inv_total = vcpu_inv.get("total", 0)
                    inv_ratio = vcpu_inv.get("allocation_ratio", 1.0)
                    physical_vcpus += inv_total
                    allowed_vcpus_total += int(inv_total * inv_ratio)
            except Exception:
                _logger.warning("Placement API CPU 조회 실패 — hypervisor vcpus로 대체", exc_info=True)
                physical_vcpus = sum(h.get("vcpus", 0) or 0 for h in data)
                allowed_vcpus_total = physical_vcpus

            # GPU 인스턴스: flavor 이름에 'gpu' 포함 여부로 집계
            gpu_instances = 0
            try:
                for s in conn.compute.servers(all_projects=True):
                    flavor = getattr(s, 'flavor', {}) or {}
                    fname = flavor.get('original_name', '') or ''
                    if 'gpu' in fname.lower():
                        gpu_instances += 1
            except Exception:
                pass

            # 컨테이너 수 (Zun)
            containers_count = 0
            try:
                from app.services.zun import list_containers_admin, ZunServiceUnavailable
                containers_count = len(list_containers_admin(conn))
            except Exception:
                pass

            # 공유 스토리지 수 (Manila)
            shares_count = 0
            try:
                shares_count = len(manila.list_shares(conn, all_tenants=True))
            except Exception:
                pass

            return {
                "hypervisor_count": host_count,
                "running_vms": running_vms,
                "gpu_instances": gpu_instances,
                "vcpus": {"total": physical_vcpus, "allowed": allowed_vcpus_total, "used": used_vcpus},
                "ram_gb": {"total": round(total_ram / 1024, 1), "used": round(used_ram / 1024, 1)},
                "disk_gb": {"total": total_disk, "used": used_disk},
                "containers_count": containers_count,
                "shares_count": shares_count,
            }
        return await asyncio.to_thread(_collect)
    except Exception as e:
        _logger.warning("admin overview 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="개요 조회 실패")


@router.get("/hypervisors", dependencies=[Depends(require_admin)])
async def list_hypervisors(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """컴퓨트 하이퍼바이저 목록."""
    try:
        def _list():
            data = _fetch_hypervisors_raw(conn)
            return [
                {
                    "id": h.get("id", ""),
                    "name": h.get("hypervisor_hostname", ""),
                    "state": h.get("state", ""),
                    "status": h.get("status", ""),
                    "hypervisor_type": h.get("hypervisor_type", ""),
                    "vcpus": h.get("vcpus", 0) or 0,
                    "vcpus_used": h.get("vcpus_used", 0) or 0,
                    "memory_size_mb": h.get("memory_mb", 0) or 0,
                    "memory_used_mb": h.get("memory_mb_used", 0) or 0,
                    "local_disk_gb": h.get("local_gb", 0) or 0,
                    "local_disk_used_gb": h.get("local_gb_used", 0) or 0,
                    "running_vms": h.get("running_vms", 0) or 0,
                }
                for h in data
            ]
        return await asyncio.to_thread(_list)
    except Exception as e:
        _logger.warning("hypervisors 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="하이퍼바이저 조회 실패")


@router.get("/all-instances", dependencies=[Depends(require_admin)])
async def list_all_instances(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 프로젝트의 인스턴스 목록 (페이지네이션)."""
    try:
        def _list():
            kwargs: dict = {"all_projects": True, "limit": limit}
            if marker:
                kwargs["marker"] = marker
            if project_id:
                kwargs["project_id"] = project_id
            items = []
            for s in itertools.islice(conn.compute.servers(**kwargs), limit):
                fault_info = None
                if (s.status or "").upper() == "ERROR":
                    fault = getattr(s, 'fault', None)
                    if isinstance(fault, dict) and fault.get("message"):
                        fault_info = fault.get("message", "")
                host = getattr(s, 'host', None)
                if not host:
                    raw = getattr(s, '_body', {}) or {}
                    if isinstance(raw, dict):
                        host = raw.get('OS-EXT-SRV-ATTR:host')
                items.append({
                    "id": s.id,
                    "name": s.name or "",
                    "status": s.status or "",
                    "project_id": getattr(s, 'project_id', None),
                    "user_id": getattr(s, 'user_id', None),
                    "flavor": getattr(s, 'flavor', {}).get('original_name', '') if isinstance(getattr(s, 'flavor', None), dict) else '',
                    "host": host,
                    "created_at": str(s.created_at) if getattr(s, 'created_at', None) else None,
                    "fault": fault_info,
                })
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}
        return await asyncio.to_thread(_list)
    except Exception as e:
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
                    "project_id": getattr(v, 'project_id', None),
                    "created_at": str(v.created_at) if getattr(v, 'created_at', None) else None,
                }
                for v in itertools.islice(conn.block_storage.volumes(**kwargs), limit)
            ]
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail="전체 볼륨 조회 실패")


@router.get("/all-containers", dependencies=[Depends(require_admin)])
async def list_all_containers(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 컨테이너 목록 (Zun)."""
    from app.services.zun import list_containers_admin, ZunServiceUnavailable
    try:
        return await asyncio.to_thread(list_containers_admin, conn)
    except ZunServiceUnavailable:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail="컨테이너 조회 실패")


@router.get("/all-shares", dependencies=[Depends(require_admin)])
async def list_all_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 공유 스토리지 목록 (Manila)."""
    try:
        return await asyncio.to_thread(manila.list_shares, conn, None, True)
    except Exception as e:
        raise HTTPException(status_code=500, detail="공유 스토리지 조회 실패")


@router.get("/topology", response_model=TopologyData, dependencies=[Depends(require_admin)])
async def admin_topology(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 네트워크/라우터/인스턴스 토폴로지."""
    def _fetch():
        topo = neutron.get_topology(conn)
        instances = []
        for s in conn.compute.servers(details=True, all_projects=True):
            addresses = getattr(s, 'addresses', {}) or {}
            instances.append(TopologyInstance(
                id=s.id,
                name=s.name or "",
                status=s.status or "",
                network_names=list(set(addresses.keys())),
                ip_addresses=[
                    {"addr": addr["addr"], "type": addr.get("OS-EXT-IPS:type", ""), "network_name": net_name}
                    for net_name, addrs in addresses.items()
                    for addr in addrs
                ],
            ))
        topo.instances = instances
        return topo.model_dump()
    try:
        return await cached_call("union:admin:topology", 30, _fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail="토폴로지 조회 실패")


@router.get("/timeseries/{resource_type}", dependencies=[Depends(require_admin)])
async def get_timeseries(
    resource_type: str,
    range: str = Query(default="7d", pattern="^(1d|2d|7d|30d)$"),
):
    """리소스 유형별 시계열 스냅샷 반환."""
    from app.services import timeseries
    valid = {"instances", "volumes", "shares", "networks"}
    if resource_type not in valid:
        raise HTTPException(status_code=400, detail=f"resource_type은 {valid} 중 하나여야 합니다")
    return await timeseries.get_timeseries(resource_type, range)


@router.get("/all-networks", dependencies=[Depends(require_admin)])
async def list_all_networks(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 네트워크 목록."""
    try:
        return await asyncio.to_thread(neutron.list_networks, conn, None)
    except Exception:
        raise HTTPException(status_code=500, detail="네트워크 목록 조회 실패")


@router.get("/all-floating-ips", dependencies=[Depends(require_admin)])
async def list_all_floating_ips(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 Floating IP 목록."""
    try:
        return await asyncio.to_thread(neutron.list_floating_ips, conn, None)
    except Exception:
        raise HTTPException(status_code=500, detail="Floating IP 목록 조회 실패")


@router.get("/all-routers", dependencies=[Depends(require_admin)])
async def list_all_routers(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 라우터 목록."""
    try:
        return await asyncio.to_thread(neutron.list_routers, conn, None)
    except Exception:
        raise HTTPException(status_code=500, detail="라우터 목록 조회 실패")


@router.get("/all-ports", dependencies=[Depends(require_admin)])
async def list_all_ports(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """전체 프로젝트의 포트 목록."""
    try:
        def _list():
            return [
                {
                    "id": p.id,
                    "name": p.name or "",
                    "status": p.status or "",
                    "network_id": p.network_id,
                    "device_owner": p.device_owner or "",
                    "device_id": p.device_id or "",
                    "mac_address": p.mac_address or "",
                    "fixed_ips": p.fixed_ips or [],
                    "project_id": getattr(p, 'project_id', None),
                }
                for p in conn.network.ports()
            ]
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="포트 목록 조회 실패")


@router.get("/quotas/{project_id}", dependencies=[Depends(require_admin)])
async def get_quotas(project_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    """특정 프로젝트의 컴퓨트 쿼터 조회."""
    try:
        def _get():
            q = conn.compute.get_quota_set(project_id)
            return {
                "instances": {"limit": q.instances, "in_use": getattr(q, 'instances_used', 0)},
                "cores": {"limit": q.cores, "in_use": getattr(q, 'cores_used', 0)},
                "ram": {"limit": q.ram, "in_use": getattr(q, 'ram_used', 0)},
            }
        return await asyncio.to_thread(_get)
    except Exception as e:
        raise HTTPException(status_code=500, detail="쿼터 조회 실패")


# ===========================================================================
# 볼륨 관리 (관리자)
# ===========================================================================

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
