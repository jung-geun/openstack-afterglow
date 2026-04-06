from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.config import get_settings
from app.models.storage import ShareInfo, CreateShareRequest, CreateAccessRuleRequest
from app.services import manila
from app.services.cache import cached_call, invalidate

router = APIRouter()


@router.get("/quota")
async def get_share_quota(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_share_quota(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Share 쿼터 조회 실패: {e}")


@router.get("", response_model=list[ShareInfo])
async def list_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:manila:{pid}:shares", 15,
            lambda: [s.model_dump() for s in manila.list_shares(conn)]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Share 목록 조회 실패: {e}")


@router.get("/{share_id}", response_model=ShareInfo)
async def get_share(share_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.get_share(conn, share_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Share를 찾을 수 없습니다")


@router.post("", response_model=ShareInfo, status_code=201)
async def create_share(
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
            share_type=req.share_type,
            metadata=req.metadata,
        )
        await invalidate(f"union:manila:{pid}:shares")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Share 생성 실패: {e}")


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
        raise HTTPException(status_code=500, detail=f"Share 삭제 실패: {e}")


# ---------------------------------------------------------------------------
# Access Rules
# ---------------------------------------------------------------------------

@router.get("/{share_id}/access-rules")
async def list_access_rules(share_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return manila.list_access_rules(conn, share_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"접근 규칙 목록 조회 실패: {e}")


@router.post("/{share_id}/access-rules", status_code=201)
async def create_access_rule(
    share_id: str,
    req: CreateAccessRuleRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return manila.create_access_rule(conn, share_id, req.cephx_id, req.access_level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"접근 규칙 생성 실패: {e}")


@router.delete("/{share_id}/access-rules/{access_id}", status_code=204)
async def revoke_access_rule(
    share_id: str,
    access_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        manila.revoke_access_rule(conn, share_id, access_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"접근 규칙 삭제 실패: {e}")
