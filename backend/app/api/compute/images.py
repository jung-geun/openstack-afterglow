import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import openstack

from app.api.deps import get_os_conn
from app.models.compute import ImageInfo
from app.services import glance
from app.services.cache import cached_call

router = APIRouter()


class UpdateImageRequest(BaseModel):
    name: str | None = None
    os_distro: str | None = None
    os_type: str | None = None
    min_disk: int | None = None
    min_ram: int | None = None


@router.get("", response_model=list[ImageInfo])
async def list_images(conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    return await cached_call(
        f"union:glance:{pid}:images", 300,
        lambda: [img.model_dump() for img in glance.list_images(conn, pid)]
    )


@router.delete("/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        await asyncio.to_thread(glance.delete_image, conn, image_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 삭제 실패: {e}")


@router.patch("/{image_id}", response_model=ImageInfo)
async def update_image(
    image_id: str,
    req: UpdateImageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        result = await asyncio.to_thread(
            glance.update_image_metadata, conn, image_id,
            req.name, req.os_distro, req.os_type, req.min_disk, req.min_ram,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 메타데이터 수정 실패: {e}")
