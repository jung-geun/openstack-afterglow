from fastapi import APIRouter, Depends, HTTPException, Query, Request
import openstack

from app.api.deps import get_os_conn
from app.config import get_settings
from app.models.storage import ShareInfo, CreateShareRequest, CreateAccessRuleRequest
from app.rate_limit import limiter
from app.services import manila
from app.services.cache import cached_call, invalidate, ttl_fast

router = APIRouter()


@router.get("/quota")
async def get_share_quota(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_share_quota(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Share 쿼터 조회 실패")


@router.get("", response_model=list[ShareInfo])
async def list_shares(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:manila:{pid}:shares", ttl_fast(),
            lambda: [s.model_dump() for s in manila.list_shares(conn)],
            refresh=refresh,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Share 목록 조회 실패")


@router.get("/types")
async def list_share_types(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_share_types(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Share 타입 목록 조회 실패")


@router.get("/{share_id}", response_model=ShareInfo)
async def get_share(share_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_share(conn, share_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Share를 찾을 수 없습니다")


@router.post("", response_model=ShareInfo, status_code=201)
@limiter.limit("5/minute")
async def create_share(
    request: Request,
    req: CreateShareRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        settings = get_settings()
        result = manila.create_share(
            conn,
            name=req.name,
            size_gb=req.size_gb,
            share_network_id=req.share_network_id or settings.os_manila_share_network_id,
            share_type=req.share_type or settings.os_manila_share_type,
            share_proto=req.share_proto,
            metadata=req.metadata,
        )
        await invalidate(f"union:manila:{pid}:shares")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Share 생성 실패")


@router.delete("/{share_id}", status_code=204)
async def delete_share(
    share_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        manila.delete_share(conn, share_id)
        await invalidate(f"union:manila:{pid}:shares")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Share 삭제 실패")


# ---------------------------------------------------------------------------
# Access Rules
# ---------------------------------------------------------------------------

@router.get("/{share_id}/access-rules")
async def list_access_rules(share_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_access_rules(conn, share_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="접근 규칙 목록 조회 실패")


@router.post("/{share_id}/access-rules", status_code=201)
async def create_access_rule(
    share_id: str,
    req: CreateAccessRuleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return manila.create_access_rule(conn, share_id, req.access_to, req.access_level, req.access_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail="접근 규칙 생성 실패")


@router.delete("/{share_id}/access-rules/{access_id}", status_code=204)
async def revoke_access_rule(
    share_id: str,
    access_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        manila.revoke_access_rule(conn, share_id, access_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="접근 규칙 삭제 실패")
