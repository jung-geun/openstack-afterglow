from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.services import nova

router = APIRouter()


@router.get("")
async def list_keypairs(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return nova.list_keypairs(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
