from fastapi import Header, HTTPException
from typing import Optional
import openstack

from app.services import keystone


async def get_token_info(
    x_auth_token: Optional[str] = Header(None),
    x_project_id: Optional[str] = Header(None),
) -> dict:
    """모든 인증 필요 엔드포인트에서 사용하는 Depends 함수."""
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="X-Auth-Token 헤더가 필요합니다")
    try:
        return keystone.validate_token(x_auth_token, project_id=x_project_id or "")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {e}")


async def get_os_conn(
    x_auth_token: Optional[str] = Header(None),
    x_project_id: Optional[str] = Header(None),
) -> openstack.connection.Connection:
    """openstacksdk Connection 객체를 반환하는 Depends 함수.
    conn._union_token, conn._union_project_id 에 원본 크리덴셜을 저장해
    Manila 등 openstacksdk 외부 클라이언트에서 그대로 사용할 수 있도록 한다.
    """
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="X-Auth-Token 헤더가 필요합니다")
    try:
        token_info = keystone.validate_token(x_auth_token, project_id=x_project_id or "")
        scoped_token = token_info["token"]
        project_id = token_info["project_id"]
        conn = keystone.get_openstack_connection(scoped_token, project_id)
        # 프로젝트에 rescope된 토큰을 저장 (Manila 등 외부 클라이언트에서 사용)
        conn._union_token = scoped_token
        conn._union_project_id = project_id
        return conn
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {e}")
