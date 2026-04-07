from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()


@router.get("")
def get_site_config():
    """사이트 표시 이름 및 설명 반환 (인증 불필요)."""
    s = get_settings()
    return {"site_name": s.site_name, "site_description": s.site_description}
