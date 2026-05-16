from __future__ import annotations

from fastapi import HTTPException
from openstack.exceptions import ConflictException, HttpException, NotFoundException


def openstack_error_to_http(exc: Exception, is_admin: bool = False) -> HTTPException:
    """OpenStack 예외 → HTTPException 변환 유틸리티."""
    if isinstance(exc, NotFoundException):
        return HTTPException(status_code=404, detail="리소스를 찾을 수 없습니다")
    if isinstance(exc, ConflictException):
        return HTTPException(status_code=409, detail="충돌이 발생했습니다")
    if isinstance(exc, HttpException):
        return HTTPException(status_code=exc.http_status or 500, detail=str(exc))
    return HTTPException(status_code=500, detail="작업 실패")
