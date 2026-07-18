"""services.chat 피처 플래그 회귀 테스트.

관리자가 afterglow.conf [services] chat 으로 빌트인 AI 채팅을 켜고 끌 수 있다.
빌트인 채팅은 자체 백엔드(litellm 등)로 동작하므로 service_chat_enabled 단독으로 켜진다.
- 플래그 false → services.chat=false (사이드바/커맨드 팔레트 숨김)
- 플래그 true → services.chat=true (프론트 메뉴/페이지 노출)
"""

from app.config import Settings, get_settings
from app.services.site_branding import configured_public_site_config


def _settings_with(**overrides) -> Settings:
    return get_settings().model_copy(update=overrides)


def test_services_chat_false_when_flag_disabled():
    s = _settings_with(service_chat_enabled=False)
    assert configured_public_site_config(s)["services"]["chat"] is False


def test_services_chat_true_when_flag_enabled():
    """빌트인 채팅 — 플래그만 켜면 활성(핵심 회귀: 프론트 메뉴 노출)."""
    s = _settings_with(service_chat_enabled=True)
    assert configured_public_site_config(s)["services"]["chat"] is True


def test_service_chat_enabled_defaults_false():
    """[services] chat 미설정 시 기본 비활성화 — 다른 서비스 플래그와 동일 컨벤션."""
    assert Settings.model_fields["service_chat_enabled"].default is False


def test_chat_router_mounted_when_enabled():
    """conftest가 SERVICE_CHAT_ENABLED=true 를 주입하므로 앱에 chat 라우트가 존재해야 한다."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/api/v1/chat") for p in paths)
