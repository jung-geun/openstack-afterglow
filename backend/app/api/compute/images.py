from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_os_conn, get_token_info
from app.models.compute import ImageDetail, ImageInfo
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


class UpdatePropertiesRequest(BaseModel):
    """이미지 임의 메타데이터 추가/수정/삭제."""

    set: dict[str, str] | None = None
    remove: list[str] | None = None


@router.get("", response_model=list[ImageInfo])
async def list_images(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._afterglow_project_id
    return await cached_call(
        f"afterglow:glance:{pid}:images",
        ttl_static(),
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
    except Exception:
        raise HTTPException(status_code=500, detail="이미지 삭제 실패")


@router.patch("/{image_id}", response_model=ImageInfo)
async def update_image(
    image_id: str,
    req: UpdateImageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        result = await asyncio.to_thread(
            glance.update_image_metadata,
            conn,
            image_id,
            req.name,
            req.os_distro,
            req.os_type,
            req.min_disk,
            req.min_ram,
            req.visibility,
        )
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="이미지 메타데이터 수정 실패")


@router.patch("/{image_id}/properties", response_model=ImageDetail)
async def update_image_properties(
    image_id: str,
    req: UpdatePropertiesRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """이미지 임의 properties 추가/수정/삭제. 소유자 또는 시스템 관리자만 가능."""
    try:
        img = await asyncio.to_thread(conn.image.get_image, image_id)
    except Exception:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")
    is_admin = token_info.get("is_system_admin", False)
    if not is_admin and img.owner != conn._afterglow_project_id:
        raise HTTPException(status_code=403, detail="본인 소유 이미지만 수정할 수 있습니다")
    try:
        return await asyncio.to_thread(
            glance.update_image_properties,
            conn,
            image_id,
            req.set,
            req.remove,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"properties 수정 실패: {e}")


# ---------------------------------------------------------------------------
# 이미지 멤버 (공유 프로젝트 관리)
# ---------------------------------------------------------------------------


class AddMemberRequest(BaseModel):
    member: str  # project_id


@router.post("/{image_id}/deactivate", status_code=200)
async def deactivate_own_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """본인 프로젝트가 소유한 이미지를 비활성화."""
    try:
        img = await asyncio.to_thread(conn.image.get_image, image_id)
    except Exception:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")
    if img.owner != conn._afterglow_project_id:
        raise HTTPException(status_code=403, detail="본인 소유 이미지만 변경할 수 있습니다")
    try:
        await asyncio.to_thread(glance.deactivate_image, conn, image_id)
        return {"status": "deactivated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"비활성화 실패: {e}")


@router.post("/{image_id}/reactivate", status_code=200)
async def reactivate_own_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """본인 프로젝트가 소유한 이미지를 활성화."""
    try:
        img = await asyncio.to_thread(conn.image.get_image, image_id)
    except Exception:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")
    if img.owner != conn._afterglow_project_id:
        raise HTTPException(status_code=403, detail="본인 소유 이미지만 변경할 수 있습니다")
    try:
        await asyncio.to_thread(glance.reactivate_image, conn, image_id)
        return {"status": "active"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"활성화 실패: {e}")


# ---------------------------------------------------------------------------
# 이미지 멤버 (공유 프로젝트 관리)
# ---------------------------------------------------------------------------


@router.get("/{image_id}/members")
async def list_image_members(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 공유 멤버(프로젝트) 목록 조회."""
    try:
        return await asyncio.to_thread(glance.list_image_members, conn, image_id)
    except Exception:
        raise HTTPException(status_code=500, detail="멤버 목록 조회 실패")


@router.post("/{image_id}/members", status_code=201)
async def add_image_member(
    image_id: str,
    req: AddMemberRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지에 공유 프로젝트 추가."""
    try:
        return await asyncio.to_thread(glance.add_image_member, conn, image_id, req.member)
    except Exception:
        raise HTTPException(status_code=500, detail="멤버 추가 실패")


@router.delete("/{image_id}/members/{member_id}", status_code=204)
async def remove_image_member(
    image_id: str,
    member_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지에서 공유 프로젝트 삭제."""
    try:
        await asyncio.to_thread(glance.remove_image_member, conn, image_id, member_id)
    except Exception:
        raise HTTPException(status_code=500, detail="멤버 삭제 실패")
