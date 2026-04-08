"""관리자 Identity 관리 엔드포인트 (사용자, 프로젝트, 쿼터, 그룹, 역할)."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn, get_token_info, require_admin

_logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Users
# ============================================================================

class CreateUserRequest(BaseModel):
    name: str
    email: str | None = None
    password: str | None = None
    enabled: bool = True
    domain_id: str | None = None


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    enabled: bool | None = None


@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """사용자 목록 (페이지네이션)."""
    def _list():
        kwargs: dict = {"limit": limit}
        if marker:
            kwargs["marker"] = marker
        users = []
        for u in conn.identity.users(**kwargs):
            users.append({
                "id": u.id,
                "name": u.name or "",
                "email": getattr(u, 'email', '') or "",
                "enabled": u.is_enabled,
                "domain_id": getattr(u, 'domain_id', None),
                "default_project_id": getattr(u, 'default_project_id', None),
                "created_at": str(u.created_at) if hasattr(u, 'created_at') and u.created_at else None,
            })
            if len(users) >= limit:
                break
        next_marker = users[-1]["id"] if len(users) == limit else None
        return {"items": users, "next_marker": next_marker, "count": len(users)}
    try:
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="사용자 목록 조회 실패")


@router.post("/users", dependencies=[Depends(require_admin)], status_code=201)
async def create_user(
    req: CreateUserRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """사용자 생성."""
    def _create():
        try:
            kwargs = {"name": req.name, "enabled": req.enabled}
            if req.email:
                kwargs["email"] = req.email
            if req.password:
                kwargs["password"] = req.password
            if req.domain_id:
                kwargs["domain_id"] = req.domain_id
            u = conn.identity.create_user(**kwargs)
            return {
                "id": u.id,
                "name": u.name or "",
                "email": getattr(u, 'email', '') or "",
                "enabled": u.is_enabled,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"사용자 생성 실패: {e}")
    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.patch("/users/{user_id}", dependencies=[Depends(require_admin)])
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """사용자 수정."""
    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.email is not None:
            kwargs["email"] = req.email
        if req.enabled is not None:
            kwargs["enabled"] = req.enabled
        try:
            u = conn.identity.update_user(user_id, **kwargs)
            return {
                "id": u.id,
                "name": u.name or "",
                "email": getattr(u, 'email', '') or "",
                "enabled": u.is_enabled,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"사용자 수정 실패: {e}")
    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


# ============================================================================
# Projects
# ============================================================================

class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    domain_id: str | None = None
    enabled: bool = True


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None


@router.get("/projects", dependencies=[Depends(require_admin)])
async def list_projects(
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 목록 (페이지네이션)."""
    def _list():
        kwargs: dict = {"limit": limit}
        if marker:
            kwargs["marker"] = marker
        projects = []
        for p in conn.identity.projects(**kwargs):
            projects.append({
                "id": p.id,
                "name": p.name or "",
                "description": getattr(p, 'description', '') or "",
                "enabled": p.is_enabled,
                "domain_id": getattr(p, 'domain_id', None),
                "created_at": str(p.created_at) if hasattr(p, 'created_at') and p.created_at else None,
            })
            if len(projects) >= limit:
                break
        next_marker = projects[-1]["id"] if len(projects) == limit else None
        return {"items": projects, "next_marker": next_marker, "count": len(projects)}
    try:
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="프로젝트 목록 조회 실패")


@router.post("/projects", dependencies=[Depends(require_admin)], status_code=201)
async def create_project(
    req: CreateProjectRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 생성."""
    def _create():
        try:
            kwargs = {"name": req.name, "enabled": req.enabled}
            if req.description:
                kwargs["description"] = req.description
            if req.domain_id:
                kwargs["domain_id"] = req.domain_id
            p = conn.identity.create_project(**kwargs)
            return {
                "id": p.id,
                "name": p.name or "",
                "description": getattr(p, 'description', '') or "",
                "enabled": p.is_enabled,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"프로젝트 생성 실패: {e}")
    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.patch("/projects/{project_id}", dependencies=[Depends(require_admin)])
async def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 수정."""
    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.description is not None:
            kwargs["description"] = req.description
        if req.enabled is not None:
            kwargs["enabled"] = req.enabled
        try:
            p = conn.identity.update_project(project_id, **kwargs)
            return {
                "id": p.id,
                "name": p.name or "",
                "description": getattr(p, 'description', '') or "",
                "enabled": p.is_enabled,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"프로젝트 수정 실패: {e}")
    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


# ============================================================================
# Quotas
# ============================================================================

class QuotaUpdateRequest(BaseModel):
    instances: int | None = None
    cores: int | None = None
    ram: int | None = None
    volumes: int | None = None
    gigabytes: int | None = None


@router.get("/quotas/{project_id}", dependencies=[Depends(require_admin)])
async def get_project_quotas(
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 쿼터 조회 (Compute + Volume)."""
    def _get():
        result: dict = {"compute": {}, "volume": {}}
        # Compute quotas
        try:
            q = conn.compute.get_quota_set(project_id)
            result["compute"] = {
                "instances": {"limit": q.instances, "in_use": getattr(q, 'instances_used', 0)},
                "cores": {"limit": q.cores, "in_use": getattr(q, 'cores_used', 0)},
                "ram": {"limit": q.ram, "in_use": getattr(q, 'ram_used', 0)},
            }
        except Exception:
            result["compute"] = {}
        # Volume quotas
        try:
            vq = conn.block_storage.get_quota_set(project_id)
            result["volume"] = {
                "volumes": {"limit": getattr(vq, 'volumes', 0), "in_use": getattr(vq, 'volumes_used', 0)},
                "gigabytes": {"limit": getattr(vq, 'gigabytes', 0), "in_use": getattr(vq, 'gigabytes_used', 0)},
            }
        except Exception:
            result["volume"] = {}
        return result
    try:
        return await asyncio.to_thread(_get)
    except Exception:
        raise HTTPException(status_code=500, detail="쿼터 조회 실패")


@router.put("/quotas/{project_id}", dependencies=[Depends(require_admin)])
async def update_project_quotas(
    project_id: str,
    req: QuotaUpdateRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 쿼터 수정."""
    def _update():
        try:
            # Compute quotas
            compute_kwargs: dict = {}
            if req.instances is not None:
                compute_kwargs["instances"] = req.instances
            if req.cores is not None:
                compute_kwargs["cores"] = req.cores
            if req.ram is not None:
                compute_kwargs["ram"] = req.ram
            if compute_kwargs:
                conn.compute.update_quota_set(project_id, **compute_kwargs)

            # Volume quotas
            volume_kwargs: dict = {}
            if req.volumes is not None:
                volume_kwargs["volumes"] = req.volumes
            if req.gigabytes is not None:
                volume_kwargs["gigabytes"] = req.gigabytes
            if volume_kwargs:
                conn.block_storage.update_quota_set(project_id, **volume_kwargs)

            return {"status": "updated"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"쿼터 수정 실패: {e}")
    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


# ============================================================================
# Groups
# ============================================================================

@router.get("/groups", dependencies=[Depends(require_admin)])
async def list_groups(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """그룹 목록."""
    def _list():
        groups = []
        try:
            for g in conn.identity.groups():
                groups.append({
                    "id": g.id,
                    "name": g.name or "",
                    "description": getattr(g, 'description', '') or "",
                    "domain_id": getattr(g, 'domain_id', None),
                })
        except Exception:
            pass
        return groups
    try:
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="그룹 목록 조회 실패")


# ============================================================================
# Roles
# ============================================================================

@router.get("/roles", dependencies=[Depends(require_admin)])
async def list_roles(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """역할 목록."""
    def _list():
        roles = []
        try:
            for r in conn.identity.roles():
                roles.append({
                    "id": r.id,
                    "name": r.name or "",
                    "domain_id": getattr(r, 'domain_id', None),
                })
        except Exception:
            pass
        return roles
    try:
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="역할 목록 조회 실패")


class AssignRoleRequest(BaseModel):
    user_id: str
    project_id: str
    role_id: str


@router.post("/roles/assign", dependencies=[Depends(require_admin)])
async def assign_role(
    req: AssignRoleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """역할 할당."""
    def _assign():
        try:
            conn.identity.assign_project_role_to_user(req.project_id, req.user_id, req.role_id)
            return {"status": "assigned"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"역할 할당 실패: {e}")
    try:
        return await asyncio.to_thread(_assign)
    except HTTPException:
        raise


@router.delete("/roles/assign", dependencies=[Depends(require_admin)])
async def revoke_role(
    user_id: str = Query(...),
    project_id: str = Query(...),
    role_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """역할 회수."""
    def _revoke():
        try:
            conn.identity.unassign_project_role_from_user(project_id, user_id, role_id)
            return {"status": "revoked"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"역할 회수 실패: {e}")
    try:
        return await asyncio.to_thread(_revoke)
    except HTTPException:
        raise