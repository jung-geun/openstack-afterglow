"""Waygate public service availability regression tests."""

from app.config import Settings, get_settings
from app.services.site_branding import configured_public_site_config


def _settings_with(**overrides) -> Settings:
    return get_settings().model_copy(update=overrides)


def test_services_waygate_false_when_flag_disabled():
    s = _settings_with(service_waygate_enabled=False)
    assert configured_public_site_config(s)["services"]["waygate"] is False


def test_services_waygate_true_when_flag_enabled():
    s = _settings_with(service_waygate_enabled=True)
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
