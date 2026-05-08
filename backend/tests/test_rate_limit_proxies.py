"""rate_limit._get_real_ip — trusted_proxies 신뢰 모델 검증.

신뢰 목록에 없는 호스트에서 들어온 X-Forwarded-For / X-Real-IP 는 무시되어야 한다
(IP spoofing 차단).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_request(remote: str, xff: str | None = None, real_ip: str | None = None):
    headers = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    req = MagicMock()
    req.headers = headers
    req.client = MagicMock()
    req.client.host = remote
    return req


def test_real_ip_uses_direct_when_proxy_not_trusted():
    """직접 연결 IP 가 trusted_proxies 에 없으면 X-Forwarded-For 무시."""
    from app.rate_limit import _get_real_ip

    mock_settings = MagicMock()
    mock_settings.trusted_proxies = "127.0.0.1/32"
    req = _make_request(remote="203.0.113.5", xff="1.1.1.1, 2.2.2.2")
    with patch("app.config.get_settings", return_value=mock_settings):
        ip = _get_real_ip(req)
    assert ip == "203.0.113.5"


def test_real_ip_trusts_xff_from_loopback():
    """trusted_proxies 안의 IP 에서 들어온 XFF 는 신뢰."""
    from app.rate_limit import _get_real_ip

    mock_settings = MagicMock()
    mock_settings.trusted_proxies = "127.0.0.1/32"
    # 2개 이상이면 rightmost-1 사용 — HAProxy 가 본 client
    req = _make_request(remote="127.0.0.1", xff="1.1.1.1, 8.8.8.8")
    with patch("app.config.get_settings", return_value=mock_settings):
        ip = _get_real_ip(req)
    assert ip == "1.1.1.1"


def test_real_ip_empty_trusted_proxies_ignores_headers():
    """trusted_proxies 가 비어 있으면 어떤 호스트의 헤더도 신뢰 안 함."""
    from app.rate_limit import _get_real_ip

    mock_settings = MagicMock()
    mock_settings.trusted_proxies = ""
    req = _make_request(remote="127.0.0.1", xff="evil-ip.example", real_ip="9.9.9.9")
    with patch("app.config.get_settings", return_value=mock_settings):
        ip = _get_real_ip(req)
    assert ip == "127.0.0.1"


def test_real_ip_xff_single_value_from_trusted():
    """trusted proxy 에서 들어온 단일 XFF 는 그대로 사용."""
    from app.rate_limit import _get_real_ip

    mock_settings = MagicMock()
    mock_settings.trusted_proxies = "10.0.0.0/8"
    req = _make_request(remote="10.42.0.5", xff="203.0.113.99")
    with patch("app.config.get_settings", return_value=mock_settings):
        ip = _get_real_ip(req)
    assert ip == "203.0.113.99"
