from fastapi import APIRouter, Depends
import openstack

from app.api.deps import get_os_conn
from app.models.storage import LibraryConfig, ShareInfo
from app.services import libraries as lib_svc, manila

router = APIRouter()


@router.get("", response_model=list[LibraryConfig])
async def list_libraries(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """사용 가능한 라이브러리 목록 (사전 빌드 share 가용 여부 포함)."""
    catalog = lib_svc.get_all()

    # 사전 빌드된 share 목록에서 library_name 매핑
    try:
        prebuilt_shares = manila.list_shares(conn, metadata_filter={"union_type": "prebuilt"})
        prebuilt_map = {s.library_name: s.id for s in prebuilt_shares if s.library_name}
    except Exception:
        prebuilt_map = {}

    result = []
    for lib in catalog:
        share_id = prebuilt_map.get(lib.id)
        result.append(LibraryConfig(
            **lib.model_dump(exclude={"share_id", "available_prebuilt"}),
            share_id=share_id,
            available_prebuilt=share_id is not None,
        ))
    return result


@router.get("/shares", response_model=list[ShareInfo])
async def list_prebuilt_shares(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """사전 빌드된 라이브러리 share 목록."""
    return manila.list_shares(conn, metadata_filter={"union_type": "prebuilt"})
