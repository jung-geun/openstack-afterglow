import asyncio
import urllib.parse

import openstack
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_os_conn
from app.models.storage import CreateContainerRequest

router = APIRouter()


# ---------------------------------------------------------------------------
# 계정 메타데이터
# ---------------------------------------------------------------------------


@router.get("/account")
async def get_object_storage_account(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 계정의 Swift 오브젝트 스토리지 사용량 메타데이터."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_account_metadata, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 계정 정보 조회 실패")


# ---------------------------------------------------------------------------
# 컨테이너 목록 / 생성
# ---------------------------------------------------------------------------


@router.get("")
async def list_object_storage_containers(
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """현재 계정의 Swift 오브젝트 스토리지 컨테이너 목록."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.list_containers, conn)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 스토리지 컨테이너 목록 조회 실패")


@router.post("", status_code=201)
async def create_object_storage_container(
    req: CreateContainerRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 스토리지 컨테이너(버킷) 생성."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.create_container, conn, req.name)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 생성 실패")


# ---------------------------------------------------------------------------
# 개별 컨테이너 — 상세 / 삭제
# ---------------------------------------------------------------------------


@router.get("/{container_name}")
async def get_object_storage_container(
    container_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """컨테이너 메타데이터(오브젝트 수, 바이트 등) 조회."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_container_metadata, conn, container_name)
    except Exception:
        raise HTTPException(status_code=404, detail="컨테이너를 찾을 수 없습니다")


@router.delete("/{container_name}", status_code=204)
async def delete_object_storage_container(
    container_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 스토리지 컨테이너 삭제 (비어있어야 함)."""
    from app.services import swift

    try:
        await asyncio.to_thread(swift.delete_container, conn, container_name)
    except Exception:
        raise HTTPException(status_code=500, detail="컨테이너 삭제 실패")


# ---------------------------------------------------------------------------
# 오브젝트 목록 / 업로드
# ---------------------------------------------------------------------------


@router.get("/{container_name}/objects")
async def list_objects(
    container_name: str,
    prefix: str = Query(default=""),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """컨테이너 내 오브젝트 목록."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.list_objects, conn, container_name, prefix)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 목록 조회 실패")


@router.post("/{container_name}/objects", status_code=201)
async def upload_object(
    container_name: str,
    file: UploadFile,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 업로드 (multipart/form-data)."""
    from app.services import swift

    try:
        data = await file.read()
        object_name = file.filename or "unnamed"
        content_type = file.content_type or ""
        return await asyncio.to_thread(swift.upload_object, conn, container_name, object_name, data, content_type)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 업로드 실패")


# ---------------------------------------------------------------------------
# 개별 오브젝트 — 다운로드 / 삭제 / 메타데이터
# (오브젝트 이름에 '/' 포함 가능 → :path 타입 사용)
# ---------------------------------------------------------------------------


@router.get("/{container_name}/objects/{object_name:path}/download")
async def download_object(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 스트리밍 다운로드."""
    from app.services import swift

    try:
        # stream_object 는 동기 함수이므로 to_thread 에서 실행
        chunks, content_type, content_length = await asyncio.to_thread(
            swift.stream_object, conn, container_name, object_name
        )
        filename = urllib.parse.quote(object_name.split("/")[-1])
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        if content_length:
            headers["Content-Length"] = str(content_length)

        def _iter():
            yield from chunks

        return StreamingResponse(_iter(), media_type=content_type, headers=headers)
    except Exception:
        raise HTTPException(status_code=404, detail="오브젝트를 찾을 수 없습니다")


@router.delete("/{container_name}/objects/{object_name:path}", status_code=204)
async def delete_object(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 삭제."""
    from app.services import swift

    try:
        await asyncio.to_thread(swift.delete_object, conn, container_name, object_name)
    except Exception:
        raise HTTPException(status_code=500, detail="오브젝트 삭제 실패")


@router.get("/{container_name}/objects/{object_name:path}/metadata")
async def get_object_metadata(
    container_name: str,
    object_name: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """오브젝트 상세 메타데이터."""
    from app.services import swift

    try:
        return await asyncio.to_thread(swift.get_object_metadata, conn, container_name, object_name)
    except Exception:
        raise HTTPException(status_code=404, detail="오브젝트를 찾을 수 없습니다")
