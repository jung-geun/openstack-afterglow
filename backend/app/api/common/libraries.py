import openstack
from fastapi import APIRouter, Depends

from app.api.deps import get_os_conn
from app.models.storage import FileStorageInfo, LibraryConfig
from app.services import libraries as lib_svc
from app.services import manila

router = APIRouter()


@router.get("", response_model=list[LibraryConfig])
async def list_libraries(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """사용 가능한 라이브러리 목록 (사전 빌드 파일 스토리지 가용 여부 포함)."""
    catalog = lib_svc.get_all()

    # 사전 빌드된 파일 스토리지 목록에서 library_name 매핑
    try:
        prebuilt_file_storages = manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt"})
        prebuilt_map = {s.library_name: s.id for s in prebuilt_file_storages if s.library_name}
    except Exception:
        prebuilt_map = {}

    result = []
    for lib in catalog:
        file_storage_id = prebuilt_map.get(lib.id)
        result.append(
            LibraryConfig(
                **lib.model_dump(exclude={"file_storage_id", "available_prebuilt"}),
                file_storage_id=file_storage_id,
                available_prebuilt=file_storage_id is not None,
            )
        )
    return result


@router.get("/file-storages", response_model=list[FileStorageInfo])
async def list_prebuilt_file_storages(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """사전 빌드된 라이브러리 파일 스토리지 목록."""
    return manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt"})
