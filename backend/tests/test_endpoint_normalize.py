"""_endpoint.py 정규화 헬퍼 단위 테스트."""

import pytest

from app.services._endpoint import normalize_endpoint, normalize_keystone_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 빈 문자열 / 공백: 그대로 통과
        ("", ""),
        ("   ", "   "),
        # version path 미입력 → /v3 자동 부착
        ("https://k", "https://k/v3"),
        ("https://k/", "https://k/v3"),
        ("https://k.example.com:5000", "https://k.example.com:5000/v3"),
        ("https://k.example.com:5000/", "https://k.example.com:5000/v3"),
        # 이미 /v3 명시 → trailing slash만 제거
        ("https://k/v3", "https://k/v3"),
        ("https://k/v3/", "https://k/v3"),
        ("https://k:5000/v3", "https://k:5000/v3"),
        ("https://k:5000/v3/", "https://k:5000/v3"),
        # 사용자가 명시한 다른 버전 → 존중 (v2 강제 치환 안 함)
        ("https://k/v2.0", "https://k/v2.0"),
        ("https://k/v2.0/", "https://k/v2.0"),
        ("https://k/v3.14", "https://k/v3.14"),
    ],
)
def test_normalize_keystone_url(raw: str, expected: str) -> None:
    assert normalize_keystone_url(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", ""),
        ("   ", "   "),
        ("https://m/v2/proj-id", "https://m/v2/proj-id"),
        ("https://m/v2/proj-id/", "https://m/v2/proj-id"),
        ("https://m/v2/", "https://m/v2"),
        ("https://m", "https://m"),
    ],
)
def test_normalize_endpoint(raw: str, expected: str) -> None:
    assert normalize_endpoint(raw) == expected
