"""common/site.py 엔드포인트 단위 테스트 (1개 public 엔드포인트)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.common.site import SiteServicesResponse
from app.config import get_settings
from app.main import app
from app.services.site_branding import configured_public_site_config


@pytest.mark.asyncio
async def test_get_site_config_public():
    """GET /api/site-config — 인증 불필요, 항상 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/site-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "site_name" in data
    assert "services" in data


@pytest.mark.asyncio
async def test_get_site_config_contains_service_flags():
    """서비스 플래그 필드 확인."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/site-config")
    services = resp.json()["services"]
    assert "manila" in services
    assert "magnum" in services
    assert "zun" in services
    assert "k3s" in services


def test_service_flag_response_model_matches_producer():
    """SiteServicesResponse 필드와 configured_public_site_config()의 services 키가 일치해야 한다.

    회귀 방지: 응답 모델에만 플래그를 추가하고 생산자를 갱신하지 않으면
    GET /api/v1/site-config 가 ResponseValidationError 로 500 을 낸다.
    (실제 발생 사례: services.mcp 를 모델에만 추가해 전체 사이트 로딩이 깨짐)
    """
    model_fields = set(SiteServicesResponse.model_fields.keys())
    produced = set(configured_public_site_config(get_settings())["services"].keys())
    assert model_fields == produced, (
        f"응답 모델에만 있음: {sorted(model_fields - produced)} / 생산자에만 있음: {sorted(produced - model_fields)}"
    )


def test_service_flags_serialize_without_validation_error():
    """생산된 services dict 가 응답 모델로 그대로 직렬화되어야 한다."""
    SiteServicesResponse(**configured_public_site_config(get_settings())["services"])
