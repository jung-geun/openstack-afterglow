"""관리자 Identity 관리 엔드포인트 (사용자, 프로젝트, 쿼터, 그룹, 역할)."""
import asyncio
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Query
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
    password: str | None = None


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
        if req.password is not None:
            kwargs["password"] = req.password
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


@router.get("/projects/names", dependencies=[Depends(require_admin)])
async def list_project_names(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """모든 프로젝트의 id/name 목록 (페이지네이션 없이)."""
    def _list():
        return [{"id": p.id, "name": p.name or ""} for p in conn.identity.projects()]
    try:
        return await asyncio.to_thread(_list)
    except Exception:
        raise HTTPException(status_code=500, detail="프로젝트 이름 목록 조회 실패")


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


@router.delete("/projects/{project_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_project(
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트 삭제."""
    def _delete():
        try:
            conn.identity.delete_project(project_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"프로젝트 삭제 실패: {e}")
    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.get("/projects/{project_id}/members", dependencies=[Depends(require_admin)])
async def list_project_members(
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """프로젝트의 사용자-역할 할당 목록 조회."""
    def _list():
        try:
            import re as _re
            raw_ep = conn.session.get_endpoint(service_type='identity', interface='public').rstrip('/')
            # /v3 또는 /v3/{project_id}를 제거 후 명시적으로 /v3 추가
            base_ep = _re.sub(r'/v[0-9.]+(?:/[a-f0-9\-]+)?$', '', raw_ep)
            endpoint = base_ep + '/v3'
            resp = conn.session.get(
                f"{endpoint}/role_assignments",
                params={"scope.project.id": project_id, "include_names": "true"},
            )
            raw = resp.json().get("role_assignments", [])
            assignments = []
            for ra in raw:
                user = ra.get("user", {})
                group = ra.get("group", {})
                role = ra.get("role", {})
                if user.get("id"):
                    assignments.append({
                        "user_id": user["id"],
                        "user_name": user.get("name", ""),
                        "role_id": role.get("id", ""),
                        "role_name": role.get("name", ""),
                        "type": "user",
                    })
                elif group.get("id"):
                    assignments.append({
                        "user_id": f"group:{group['id']}",
                        "user_name": f"[그룹] {group.get('name', '')}",
                        "role_id": role.get("id", ""),
                        "role_name": role.get("name", ""),
                        "type": "group",
                        "group_id": group["id"],
                    })
            return assignments
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"멤버 목록 조회 실패: {e}")
    try:
        return await asyncio.to_thread(_list)
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


class CreateGroupRequest(BaseModel):
    name: str
    description: str | None = None
    domain_id: str | None = None


class UpdateGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.post("/groups", dependencies=[Depends(require_admin)], status_code=201)
async def create_group(
    req: CreateGroupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹 생성."""
    def _create():
        try:
            kwargs = {"name": req.name}
            if req.description:
                kwargs["description"] = req.description
            if req.domain_id:
                kwargs["domain_id"] = req.domain_id
            g = conn.identity.create_group(**kwargs)
            return {
                "id": g.id,
                "name": g.name or "",
                "description": getattr(g, "description", "") or "",
                "domain_id": getattr(g, "domain_id", None),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 생성 실패: {e}")
    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise


@router.patch("/groups/{group_id}", dependencies=[Depends(require_admin)])
async def update_group(
    group_id: str,
    req: UpdateGroupRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹 수정."""
    def _update():
        kwargs: dict = {}
        if req.name is not None:
            kwargs["name"] = req.name
        if req.description is not None:
            kwargs["description"] = req.description
        try:
            g = conn.identity.update_group(group_id, **kwargs)
            return {
                "id": g.id,
                "name": g.name or "",
                "description": getattr(g, "description", "") or "",
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 수정 실패: {e}")
    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise


@router.delete("/groups/{group_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_group(
    group_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹 삭제."""
    def _delete():
        try:
            conn.identity.delete_group(group_id, ignore_missing=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 삭제 실패: {e}")
    try:
        await asyncio.to_thread(_delete)
    except HTTPException:
        raise


@router.get("/groups/{group_id}/users", dependencies=[Depends(require_admin)])
async def list_group_users(
    group_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹 멤버 목록."""
    def _list():
        users = []
        try:
            for u in conn.identity.group_users(group_id):
                users.append({
                    "id": u.id,
                    "name": u.name or "",
                    "email": getattr(u, "email", "") or "",
                    "enabled": getattr(u, "is_enabled", True),
                })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"그룹 멤버 조회 실패: {e}")
        return users
    try:
        return await asyncio.to_thread(_list)
    except HTTPException:
        raise


@router.put("/groups/{group_id}/users/{user_id}", dependencies=[Depends(require_admin)], status_code=204)
async def add_user_to_group(
    group_id: str,
    user_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹에 사용자 추가."""
    def _add():
        try:
            conn.identity.add_user_to_group(user_id, group_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 멤버 추가 실패: {e}")
    try:
        await asyncio.to_thread(_add)
    except HTTPException:
        raise


@router.delete("/groups/{group_id}/users/{user_id}", dependencies=[Depends(require_admin)], status_code=204)
async def remove_user_from_group(
    group_id: str,
    user_id: str,
    x_auth_token: str | None = Header(None),
    x_project_id: str | None = Header(None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹에서 사용자 제거. Keystone 토큰 revocation 대비 세션 캐시 클리어."""
    def _remove():
        try:
            conn.identity.remove_user_from_group(user_id, group_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 멤버 제거 실패: {e}")
    try:
        await asyncio.to_thread(_remove)
        # 그룹 멤버십 변경 시 Keystone이 토큰을 revoke할 수 있으므로 세션 캐시 클리어
        if x_auth_token:
            import hashlib as _hl
            from app.services.cache import _get_redis
            token_hash = _hl.sha256(x_auth_token.encode()).hexdigest()[:32]
            pid = x_project_id or "noscope"
            try:
                r = await _get_redis()
                await r.delete(f"union:session:{token_hash}:{pid}")
                await r.delete(f"union:session_start:{token_hash}:{pid}")
            except Exception:
                pass
    except HTTPException:
        raise


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


class AssignGroupRoleRequest(BaseModel):
    group_id: str
    project_id: str
    role_id: str


@router.post("/roles/assign-group", dependencies=[Depends(require_admin)])
async def assign_group_role(
    req: AssignGroupRoleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹에 프로젝트 역할 할당."""
    def _assign():
        try:
            conn.identity.assign_project_role_to_group(req.project_id, req.group_id, req.role_id)
            return {"status": "assigned"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 역할 할당 실패: {e}")
    try:
        return await asyncio.to_thread(_assign)
    except HTTPException:
        raise


@router.delete("/roles/assign-group", dependencies=[Depends(require_admin)])
async def revoke_group_role(
    group_id: str = Query(...),
    project_id: str = Query(...),
    role_id: str = Query(...),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """그룹에서 프로젝트 역할 회수."""
    def _revoke():
        try:
            conn.identity.unassign_project_role_from_group(project_id, group_id, role_id)
            return {"status": "revoked"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"그룹 역할 회수 실패: {e}")
    try:
        return await asyncio.to_thread(_revoke)
    except HTTPException:
        raise