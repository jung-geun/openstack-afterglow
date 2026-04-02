from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn, get_token_info
from app.models.storage import ShareInfo
from app.services import manila, libraries as lib_svc
from app.config import get_settings

router = APIRouter()


@router.get("/shares", response_model=list[ShareInfo])
async def list_admin_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """모든 Union 관련 share 목록 (prebuilt + dynamic)."""
    return manila.list_shares(conn)


@router.post("/shares/build", status_code=202)
async def trigger_build(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
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
