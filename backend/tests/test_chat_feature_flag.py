"""services.chat 피처 플래그 회귀 테스트.

관리자가 afterglow.conf [services] chat 으로 AI 채팅(LibreChat 임베드)을 켜고 끌 수 있다.
- 플래그 false → services.chat=false (사이드바/커맨드 팔레트 숨김, 라우터 미등록)
- 플래그 true + [chat] base_url 미설정 → services.chat=false
- 플래그 true + [chat] base_url 설정 → services.chat=true
"""

from app.config import Settings, get_settings
from app.services.site_branding import configured_public_site_config


def _settings_with(**overrides) -> Settings:
    return get_settings().model_copy(update=overrides)


def test_services_chat_false_when_flag_disabled():
    """[chat] base_url이 설정돼 있어도 services.chat=false 면 기능 비활성."""
    s = _settings_with(service_chat_enabled=False, librechat_base_url="https://chat.example.com")
    assert configured_public_site_config(s)["services"]["chat"] is False


def test_services_chat_false_when_flag_enabled_but_unconfigured():
    s = _settings_with(service_chat_enabled=True, librechat_base_url="")
    assert configured_public_site_config(s)["services"]["chat"] is False


def test_services_chat_true_when_flag_enabled_and_configured():
    s = _settings_with(service_chat_enabled=True, librechat_base_url="https://chat.example.com")
    assert configured_public_site_config(s)["services"]["chat"] is True


def test_service_chat_enabled_defaults_false():
    """[services] chat 미설정 시 기본 비활성화 — 다른 서비스 플래그와 동일 컨벤션."""
    assert Settings.model_fields["service_chat_enabled"].default is False


def test_chat_router_mounted_when_enabled():
    """conftest가 SERVICE_CHAT_ENABLED=true 를 주입하므로 앱에 chat 라우트가 존재해야 한다."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/api/v1/chat") for p in paths)
