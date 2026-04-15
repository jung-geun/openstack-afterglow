import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn
from app.models.compute import ImageInfo, ImageDetail
from app.services import glance
from app.services.cache import cached_call, ttl_static

router = APIRouter()


class UpdateImageRequest(BaseModel):
    name: str | None = None
    os_distro: str | None = None
    os_type: str | None = None
    min_disk: int | None = None
    min_ram: int | None = None
    visibility: str | None = None


@router.get("", response_model=list[ImageInfo])
async def list_images(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    return await cached_call(
        f"afterglow:glance:{pid}:images", ttl_static(),
        lambda: [img.model_dump() for img in glance.list_images(conn, pid)],
        refresh=refresh,
    )


@router.get("/{image_id}", response_model=ImageDetail)
async def get_image_detail(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(glance.get_image, conn, image_id)
    except Exception:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")


@router.delete("/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(glance.delete_image, conn, image_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="이미지 삭제 실패")


@router.patch("/{image_id}", response_model=ImageInfo)
async def update_image(
    image_id: str,
    req: UpdateImageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        result = await asyncio.to_thread(
            glance.update_image_metadata, conn, image_id,
            req.name, req.os_distro, req.os_type, req.min_disk, req.min_ram, req.visibility,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="이미지 메타데이터 수정 실패")
