"""Settings.os_auth_url Pydantic validator 단위 테스트."""

from app.config import Settings


def _make(auth_url: str, manila_endpoint: str = "", swift_endpoint: str = "") -> Settings:
    return Settings(
        os_auth_url=auth_url,
        os_manila_endpoint=manila_endpoint,
        os_swift_endpoint=swift_endpoint,
    )


def test_auth_url_auto_appends_v3_when_missing() -> None:
    s = _make("https://keystone.example.com:5000")
    assert s.os_auth_url == "https://keystone.example.com:5000/v3"


def test_auth_url_preserves_explicit_v3() -> None:
    s = _make("https://keystone.example.com:5000/v3")
    assert s.os_auth_url == "https://keystone.example.com:5000/v3"


def test_auth_url_strips_trailing_slash() -> None:
    s = _make("https://keystone.example.com:5000/v3/")
    assert s.os_auth_url == "https://keystone.example.com:5000/v3"


def test_auth_url_respects_explicit_v2() -> None:
    s = _make("https://keystone.example.com/v2.0")
    assert s.os_auth_url == "https://keystone.example.com/v2.0"


def test_auth_url_empty_passthrough() -> None:
    s = _make("")
    assert s.os_auth_url == ""


def test_manila_endpoint_strips_trailing_slash() -> None:
    s = _make("", manila_endpoint="https://manila.example.com/v2/proj/")
    assert s.os_manila_endpoint == "https://manila.example.com/v2/proj"


def test_swift_endpoint_strips_trailing_slash() -> None:
    s = _make("", swift_endpoint="https://swift.example.com/v1/AUTH_proj/")
    assert s.os_swift_endpoint == "https://swift.example.com/v1/AUTH_proj"


def test_service_endpoint_empty_passthrough() -> None:
    s = _make("", manila_endpoint="", swift_endpoint="")
    assert s.os_manila_endpoint == ""
    assert s.os_swift_endpoint == ""
