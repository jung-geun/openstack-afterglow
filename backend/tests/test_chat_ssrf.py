"""커스텀 툴 SSRF 가드 테스트 — 내부/사설/메타데이터 차단, 공용 허용.

crypto 처럼 외부 인프라 불요(단, DNS 해석은 monkeypatch).
"""

import socket

import pytest

from app.services.chat import ssrf
from app.services.chat.ssrf import SsrfBlocked, validate_url


def _gai(ip: str):
    def _fn(*a, **k):
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 443))]

    return _fn


class TestScheme:
    @pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "gopher://x"])
    def test_blocks_non_http(self, url):
        with pytest.raises(SsrfBlocked):
            validate_url(url)


class TestIpLiterals:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",  # 클라우드 메타데이터
            "http://[::1]/",
            "http://0.0.0.0/",
        ],
    )
    def test_blocks_internal_ip(self, url):
        with pytest.raises(SsrfBlocked):
            validate_url(url)

    def test_allows_public_ip(self):
        assert validate_url("http://93.184.216.34/") == "http://93.184.216.34/"


class TestHostnames:
    def test_blocks_localhost(self):
        with pytest.raises(SsrfBlocked):
            validate_url("http://localhost/")

    def test_blocks_metadata_hostname(self):
        with pytest.raises(SsrfBlocked):
            validate_url("http://metadata.google.internal/")

    def test_blocks_host_resolving_to_private(self, monkeypatch):
        monkeypatch.setattr(ssrf.socket, "getaddrinfo", _gai("10.1.2.3"))
        with pytest.raises(SsrfBlocked):
            validate_url("http://evil.example.com/")

    def test_blocks_host_resolving_to_metadata(self, monkeypatch):
        monkeypatch.setattr(ssrf.socket, "getaddrinfo", _gai("169.254.169.254"))
        with pytest.raises(SsrfBlocked):
            validate_url("http://rebind.example.com/")

    def test_allows_host_resolving_public(self, monkeypatch):
        monkeypatch.setattr(ssrf.socket, "getaddrinfo", _gai("93.184.216.34"))
        assert validate_url("http://good.example.com/") == "http://good.example.com/"

    def test_blocks_unresolvable(self, monkeypatch):
        def _raise(*a, **k):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(ssrf.socket, "getaddrinfo", _raise)
        with pytest.raises(SsrfBlocked):
            validate_url("http://nonexistent.invalid/")
