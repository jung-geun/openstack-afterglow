from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.common.activity_recorder import rec
from app.api.deps import CacheMode, cache_mode, get_os_conn, get_token_info
from app.config import get_settings
from app.models.compute import ImageDetail, ImageInfo
from app.rate_limit import limiter
from app.services import glance
from app.services.cache import cached_call, invalidate, ttl_static

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
async def list_images(
    conn: openstack.connection.Connection = Depends(get_os_conn), cm: CacheMode = Depends(cache_mode)
):
    pid = conn._afterglow_project_id
    return await cached_call(
        f"afterglow:glance:{pid}:images",
        ttl_static(),
        lambda: [img.model_dump() for img in glance.list_images(conn, pid)],
        enabled=cm.enabled,
        refresh=cm.refresh,
    )


@router.post("", status_code=201)
@limiter.limit("3/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    disk_format: str = Form("raw"),
    visibility: str = Form("private"),
    os_distro: str | None = Form(None),
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """이미지 파일 업로드 (multipart/form-data). raw / qcow2 / vmdk 등 주요 포맷 지원."""
    pid = conn._afterglow_project_id

    if disk_format not in glance._ALLOWED_DISK_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 disk_format입니다. 허용: {sorted(glance._ALLOWED_DISK_FORMATS)}",
        )
    if visibility not in {"private", "public", "shared", "community"}:
        raise HTTPException(status_code=400, detail="visibility 값이 올바르지 않습니다")
    is_admin = token_info.get("is_system_admin", False)
    if visibility in {"public", "community"} and not is_admin:
        raise HTTPException(status_code=403, detail="public/community 가시성은 시스템 관리자만 설정할 수 있습니다")
    if not (name or "").strip():
        raise HTTPException(status_code=400, detail="이미지 이름이 비어 있습니다")

    settings = get_settings()
    max_bytes = settings.app_max_upload_gb * 1024**3
    incoming_size = getattr(file, "size", None)
    if incoming_size is not None and incoming_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"파일이 최대 허용 크기({settings.app_max_upload_gb}GB)를 초과합니다",
        )

    props: dict = {}
    if os_distro:
        props["os_distro"] = os_distro

    try:
        img = await asyncio.to_thread(
            glance.create_image,
            conn,
            name=name.strip(),
            disk_format=disk_format,
            visibility=visibility,
            data=file.file,
            properties=props or None,
        )
        await invalidate(f"afterglow:glance:{pid}:images")
        await rec(token_info, conn, resource_type="image", action="create", resource_id=getattr(img, "id", None))
        return {"id": img.id, "name": img.name, "status": img.status, "disk_format": img.disk_format}
    except Exception as e:
        await rec(token_info, conn, resource_type="image", action="create", status="failed", error_message=str(e)[:500])
        raise HTTPException(status_code=500, detail=f"이미지 업로드 실패: {e}")


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
