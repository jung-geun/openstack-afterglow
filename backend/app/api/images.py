from fastapi import APIRouter, Depends
import openstack

from app.api.deps import get_os_conn
from app.models.compute import ImageInfo
from app.services import glance
from app.services.cache import cached_call

router = APIRouter()


@router.get("", response_model=list[ImageInfo])
async def list_images(conn: openstack.connection.Connection = Depends(get_os_conn)):
    pid = conn._union_project_id
    return await cached_call(
        f"union:glance:{pid}:images", 300,
        lambda: [img.model_dump() for img in glance.list_images(conn)]
    )
