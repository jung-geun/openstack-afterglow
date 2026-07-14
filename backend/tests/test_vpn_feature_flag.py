"""services.vpn 피처 플래그 회귀 테스트.

관리자가 afterglow.conf [services] vpn 으로 VPN 기능을 켜고 끌 수 있다.
- 플래그 false → services.vpn=false (사이드바/페이지 게이팅, 라우터 미등록)
- 플래그 true + [vpn] 미설정 → services.vpn=false (페이지의 미설정 안내 유지)
- 플래그 true + [vpn] 설정 → services.vpn=true
"""

from app.config import Settings, get_settings
from app.services.site_branding import configured_public_site_config


def _settings_with(**overrides) -> Settings:
    return get_settings().model_copy(update=overrides)


def test_services_vpn_false_when_flag_disabled():
    """[vpn]이 설정돼 있어도 services.vpn=false 면 기능 비활성."""
    s = _settings_with(service_vpn_enabled=False, vpn_provider_network_id="net-1", vpn_image_id="img-1")
    assert configured_public_site_config(s)["services"]["vpn"] is False


def test_services_vpn_false_when_flag_enabled_but_unconfigured():
    s = _settings_with(service_vpn_enabled=True, vpn_provider_network_id="", vpn_image_id="")
    assert configured_public_site_config(s)["services"]["vpn"] is False


def test_services_vpn_true_when_flag_enabled_and_configured():
    s = _settings_with(service_vpn_enabled=True, vpn_provider_network_id="net-1", vpn_image_id="img-1")
    assert configured_public_site_config(s)["services"]["vpn"] is True


def test_service_vpn_enabled_defaults_false():
    """[services] vpn 미설정 시 기본 비활성화 — 다른 서비스 플래그와 동일 컨벤션."""
    assert Settings.model_fields["service_vpn_enabled"].default is False


def test_vpn_routers_mounted_when_enabled():
    """conftest가 SERVICE_VPN_ENABLED=true 를 주입하므로 앱에 vpn 라우트가 존재해야 한다."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/v1/vpn/servers" in paths
    assert "/api/v1/vpn/servers/{server_id}/agent/register" in paths
