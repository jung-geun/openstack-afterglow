"""관리자 Flavor 관리 엔드포인트."""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn, require_admin
from app.api.common.dashboard import _gpu_count_from_flavor

_logger = logging.getLogger(__name__)

router = APIRouter()


class CreateFlavorRequest(BaseModel):
    name: str
    vcpus: int
    ram: int  # MB
    disk: int  # GB
    is_public: bool = True
    description: str | None = None


class FlavorAccessRequest(BaseModel):
    project_id: str


class ExtraSpecRequest(BaseModel):
    key: str
    value: str


def _flavor_to_dict(f) -> dict:
    extra_specs = {}
    try:
        if hasattr(f, 'extra_specs') and f.extra_specs:
            extra_specs = dict(f.extra_specs)
    except Exception:
        pass
    gpu_count = _gpu_count_from_flavor(f.name or "", extra_specs)
    return {
        "id": f.id,
        "name": f.name or "",
        "vcpus": f.vcpus,
        "ram": f.ram,
        "disk": f.disk,
        "is_public": getattr(f, 'is_public', True),
        "description": getattr(f, 'description', None) or "",
        "extra_specs": extra_specs,
        "is_gpu": gpu_count > 0,
        "gpu_count": gpu_count,
    }


@router.get("/flavors", dependencies=[Depends(require_admin)])
async def list_admin_flavors(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    is_public: bool | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """전체 flavor 목록 (공개+비공개)."""
    def _list():
        kwargs: dict = {"details": True}
        if is_public is not None:
            kwargs["is_public"] = is_public
        else:
            kwargs["is_public"] = None  # 모든 flavor 조회
        if marker:
            kwargs["marker"] = marker
        flavors = list(conn.compute.flavors(**kwargs))
        items = [_flavor_to_dict(f) for f in flavors[:limit]]
        next_marker = items[-1]["id"] if len(items) == limit else None
        return {"items": items, "next_marker": next_marker, "count": len(items)}
    try:
        return await asyncio.to_thread(_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Flavor 목록 조회 실패")


@router.post("/flavors", dependencies=[Depends(require_admin)], status_code=201)
async def create_flavor(
    req: CreateFlavorRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor 생성."""
    def _create():
        try:
            flavor = conn.compute.create_flavor(
                name=req.name,
                vcpus=req.vcpus,
                ram=req.ram,
                disk=req.disk,
                is_public=req.is_public,
                description=req.description,
            )
            return _flavor_to_dict(flavor)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Flavor 생성 실패: {e}")
    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Flavor 생성 실패")


@router.delete("/flavors/{flavor_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_flavor(
    flavor_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor 삭제."""
    def _delete():
        try:
            conn.compute.delete_flavor(flavor_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Flavor 삭제 실패: {e}")
    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.get("/flavors/{flavor_id}/access", dependencies=[Depends(require_admin)])
async def list_flavor_access(
    flavor_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor 접근 권한이 있는 프로젝트 목록 (프로젝트 이름 포함)."""
    def _list():
        try:
            endpoint = conn.compute.get_endpoint()
            resp = conn.session.get(f"{endpoint}/flavors/{flavor_id}/os-flavor-access")
            if resp.status_code in (404, 403):
                return []
            if resp.status_code == 409:
                # public flavor — no access list
                return []
            accesses = resp.json().get("flavor_access", [])
            result = []
            for a in accesses:
                pid = a.get("tenant_id") or a.get("project_id") or ""
                project_name = ""
                try:
                    proj = conn.identity.get_project(pid)
                    project_name = proj.name or ""
                except Exception:
                    pass
                result.append({
                    "flavor_id": a.get("flavor_id", flavor_id),
                    "project_id": pid,
                    "project_name": project_name,
                })
            return result
        except Exception as e:
            _logger.warning("Flavor 접근 목록 조회 실패 (flavor_id=%s): %s", flavor_id, e)
            return []
    try:
        return await asyncio.to_thread(_list)
    except HTTPException:
        raise


@router.post("/flavors/{flavor_id}/extra-specs", dependencies=[Depends(require_admin)])
async def set_flavor_extra_spec(
    flavor_id: str,
    req: ExtraSpecRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor extra_spec 추가/수정."""
    def _set():
        try:
            conn.compute.create_flavor_extra_specs(flavor_id, {req.key: req.value})
            return {"key": req.key, "value": req.value}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"extra_spec 설정 실패: {e}")
    try:
        return await asyncio.to_thread(_set)
    except HTTPException:
        raise


@router.delete("/flavors/{flavor_id}/extra-specs/{key}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_flavor_extra_spec(
    flavor_id: str,
    key: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor extra_spec 삭제."""
    def _delete():
        try:
            conn.compute.delete_flavor_extra_specs_property(flavor_id, key)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"extra_spec 삭제 실패: {e}")
    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.post("/flavors/{flavor_id}/access", dependencies=[Depends(require_admin)])
async def add_flavor_access(
    flavor_id: str,
    req: FlavorAccessRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor에 프로젝트 접근 권한 추가 (Nova raw API)."""
    def _add():
        try:
            endpoint = conn.compute.get_endpoint()
            resp = conn.session.post(
                f"{endpoint}/flavors/{flavor_id}/action",
                json={"addTenantAccess": {"tenant": req.project_id}},
            )
            if resp.status_code >= 400:
                raise Exception(f"HTTP {resp.status_code}")
            return {"flavor_id": flavor_id, "project_id": req.project_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"접근 권한 추가 실패: {e}")
    try:
        return await asyncio.to_thread(_add)
    except HTTPException:
        raise


@router.delete("/flavors/{flavor_id}/access/{project_id}", dependencies=[Depends(require_admin)], status_code=204)
async def remove_flavor_access(
    flavor_id: str,
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """Flavor에서 프로젝트 접근 권한 제거 (Nova raw API)."""
    def _remove():
        try:
            endpoint = conn.compute.get_endpoint()
            resp = conn.session.post(
                f"{endpoint}/flavors/{flavor_id}/action",
                json={"removeTenantAccess": {"tenant": project_id}},
            )
            if resp.status_code >= 400:
                raise Exception(f"HTTP {resp.status_code}")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"접근 권한 제거 실패: {e}")
    try:
        await asyncio.to_thread(_remove)
    except HTTPException:
        raise