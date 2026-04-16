import openstack
from fastapi import APIRouter, Depends

from app.api.deps import get_os_conn
from app.models.compute import FlavorInfo
from app.services import nova

router = APIRouter()


@router.get("", response_model=list[FlavorInfo])
async def list_flavors(conn: openstack.connection.Connection = Depends(get_os_conn)):
    return nova.list_flavors(conn)
