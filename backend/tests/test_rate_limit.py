"""rate_limit._get_real_ip() 단위 테스트."""

from unittest.mock import MagicMock

from app.rate_limit import _get_real_ip


def _req(forwarded: str | None = None, real_ip: str | None = None, client_host: str = "127.0.0.1"):
    """테스트용 Request mock 생성."""
    request = MagicMock()
    headers = {}
    if forwarded is not None:
        headers["X-Forwarded-For"] = forwarded
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    request.headers = headers
    request.client = MagicMock()
    request.client.host = client_host
    return request


class TestGetRealIp:
    def test_no_headers_returns_direct_ip(self):
        """헤더 없으면 직접 연결 IP를 반환해야 한다."""
        req = _req(client_host="203.0.113.1")
        assert _get_real_ip(req) == "203.0.113.1"

    def test_single_forwarded_for_returns_it(self):
        """X-Forwarded-For 단일 값이면 그 값을 반환해야 한다 (HAProxy가 추가한 클라이언트 IP)."""
        req = _req(forwarded="203.0.113.5")
        assert _get_real_ip(req) == "203.0.113.5"

    def test_two_forwarded_for_returns_first(self):
        """X-Forwarded-For에 2개 값이면 rightmost-1(클라이언트)을 반환해야 한다."""
        # client, haproxy-added → client IP는 첫 번째
        req = _req(forwarded="203.0.113.5, 10.0.0.1")
        assert _get_real_ip(req) == "203.0.113.5"

    def test_three_forwarded_for_returns_second_from_right(self):
        """3개 이상이면 rightmost-1을 반환해야 한다."""
        req = _req(forwarded="1.2.3.4, 5.6.7.8, 10.0.0.1")
        # rightmost-1은 5.6.7.8
        assert _get_real_ip(req) == "5.6.7.8"

    def test_forwarded_for_with_spaces(self):
        """공백이 포함된 X-Forwarded-For도 올바르게 파싱되어야 한다."""
        req = _req(forwarded="  203.0.113.5  ,  10.0.0.1  ")
        assert _get_real_ip(req) == "203.0.113.5"

    def test_real_ip_header_fallback(self):
        """X-Forwarded-For 없을 때 X-Real-IP를 사용해야 한다."""
        req = _req(real_ip="203.0.113.9")
        assert _get_real_ip(req) == "203.0.113.9"

    def test_real_ip_with_spaces(self):
        """X-Real-IP의 공백도 trim해야 한다."""
        req = _req(real_ip="  10.1.2.3  ")
        assert _get_real_ip(req) == "10.1.2.3"

    def test_forwarded_for_takes_precedence_over_real_ip(self):
        """X-Forwarded-For가 X-Real-IP보다 우선해야 한다."""
        req = _req(forwarded="203.0.113.5", real_ip="9.9.9.9")
        assert _get_real_ip(req) == "203.0.113.5"

    def test_ipv6_direct(self):
        """IPv6 직접 연결 IP도 그대로 반환되어야 한다."""
        req = _req(client_host="::1")
        assert _get_real_ip(req) == "::1"

    def test_ipv6_in_forwarded_for(self):
        """X-Forwarded-For에 IPv6 포함 시 정상 파싱되어야 한다."""
        req = _req(forwarded="2001:db8::1, 10.0.0.1")
        assert _get_real_ip(req) == "2001:db8::1"
