from fastapi import APIRouter, Depends
import openstack

from app.api.deps import get_os_conn
from app.models.compute import ImageInfo
from app.services import glance

router = APIRouter()


@router.get("", response_model=list[ImageInfo])
async def list_images(conn: openstack.connection.Connection = Depends(get_os_conn)):
    return glance.list_images(conn)
