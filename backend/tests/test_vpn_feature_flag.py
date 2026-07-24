"""services.waygate 피처 플래그 회귀 테스트.

관리자가 afterglow.conf [services] waygate 으로 Waygate 기능을 켜고 끌 수 있다.
- 플래그 false → services.waygate=false (사이드바/페이지 게이팅, 라우터 미등록)
- 플래그 true + [waygate] 미설정 → services.waygate=false (페이지의 미설정 안내 유지)
- 플래그 true + [waygate] 설정 → services.waygate=true
"""

from app.config import Settings, get_settings
from app.services.site_branding import configured_public_site_config


def _settings_with(**overrides) -> Settings:
    return get_settings().model_copy(update=overrides)


def test_services_waygate_false_when_flag_disabled():
    """[waygate]이 설정돼 있어도 services.waygate=false 면 기능 비활성."""
    s = _settings_with(service_waygate_enabled=False, waygate_provider_network_id="net-1", waygate_image_id="img-1")
    assert configured_public_site_config(s)["services"]["waygate"] is False


def test_services_waygate_false_when_flag_enabled_but_unconfigured():
    s = _settings_with(service_waygate_enabled=True, waygate_provider_network_id="", waygate_image_id="")
    assert configured_public_site_config(s)["services"]["waygate"] is False


def test_services_waygate_true_when_flag_enabled_and_configured():
    s = _settings_with(service_waygate_enabled=True, waygate_provider_network_id="net-1", waygate_image_id="img-1")
    assert configured_public_site_config(s)["services"]["waygate"] is True


def test_service_waygate_enabled_defaults_false():
    """[services] waygate 미설정 시 기본 비활성화 — 다른 서비스 플래그와 동일 컨벤션."""
    assert Settings.model_fields["service_waygate_enabled"].default is False


def test_waygate_routers_mounted_when_enabled():
    """conftest가 SERVICE_WAYGATE_ENABLED=true 를 주입하면 Waygate 라우트가 존재한다."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/v1/waygate/servers" in paths
    assert "/api/v1/waygate/servers/{server_id}/agent/register" in paths
