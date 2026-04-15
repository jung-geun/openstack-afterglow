"""관리자 이미지 관리 엔드포인트."""
import asyncio
import logging
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn, require_admin
from app.services import glance
from app.services.cache import cached_call, ttl_static

_logger = logging.getLogger(__name__)

router = APIRouter()


class AdminUpdateImageRequest(BaseModel):
    name: str | None = None
    os_distro: str | None = None
    os_type: str | None = None
    min_disk: int | None = None
    min_ram: int | None = None
    visibility: str | None = None


@router.get("/images", dependencies=[Depends(require_admin)])
async def list_admin_images(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    refresh: bool = Query(False),
    limit: int = Query(default=20, ge=1, le=100),
    marker: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    """전체 이미지 목록 (visibility 무관, 페이지네이션)."""
    try:
        def _list():
            kwargs: dict = {"limit": limit}
            if marker:
                kwargs["marker"] = marker
            if search:
                kwargs["name"] = search
            items = []
            for img in conn.image.images(**kwargs):
                items.append({
                    "id": img.id,
                    "name": img.name or "",
                    "status": img.status or "",
                    "size": img.size or 0,
                    "min_disk": img.min_disk or 0,
                    "min_ram": img.min_ram or 0,
                    "disk_format": img.disk_format or "",
                    "os_distro": getattr(img, "os_distro", None) or glance._guess_distro(img.name or ""),
                    "visibility": img.visibility or "private",
                    "owner": img.owner or "",
                    "created_at": str(img.created_at) if img.created_at else None,
                    "protected": getattr(img, "is_protected", False),
                })
                if len(items) >= limit:
                    break
            next_marker = items[-1]["id"] if len(items) == limit else None
            return {"items": items, "next_marker": next_marker, "count": len(items)}
        # 마커가 없고 검색도 없을 때만 캐시 사용
        if not marker and not search:
            return await cached_call(f"afterglow:admin:images:{limit}", ttl_static(), _list, refresh=refresh)
        return await asyncio.to_thread(_list)
    except Exception:
        _logger.warning("관리자 이미지 목록 조회 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="이미지 목록 조회 실패")


@router.get("/images/{image_id}", dependencies=[Depends(require_admin)])
async def get_admin_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 상세 조회."""
    try:
        return await asyncio.to_thread(glance.get_image, conn, image_id)
    except Exception:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")


@router.patch("/images/{image_id}", dependencies=[Depends(require_admin)])
async def update_admin_image(
    image_id: str,
    req: AdminUpdateImageRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 메타데이터 수정."""
    try:
        result = await asyncio.to_thread(
            glance.update_image_metadata,
            conn, image_id, req.name, req.os_distro, req.os_type, req.min_disk, req.min_ram, req.visibility,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 수정 실패: {e}")


@router.delete("/images/{image_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_admin_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 삭제."""
    try:
        await asyncio.to_thread(glance.delete_image, conn, image_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 삭제 실패: {e}")


@router.post("/images/{image_id}/deactivate", dependencies=[Depends(require_admin)], status_code=200)
async def deactivate_admin_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 비활성화 (deactivated 상태)."""
    try:
        await asyncio.to_thread(glance.deactivate_image, conn, image_id)
        return {"status": "deactivated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 비활성화 실패: {e}")


@router.post("/images/{image_id}/reactivate", dependencies=[Depends(require_admin)], status_code=200)
async def reactivate_admin_image(
    image_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """이미지 활성화 (active 상태)."""
    try:
        await asyncio.to_thread(glance.reactivate_image, conn, image_id)
        return {"status": "active"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"이미지 활성화 실패: {e}")
