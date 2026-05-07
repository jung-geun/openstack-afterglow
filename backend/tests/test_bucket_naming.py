"""버킷 이름 검증 (Phase 10) 정책 매트릭스 테스트."""

from __future__ import annotations

import pytest

from app.services.bucket_naming import validate_bucket_name

# ---------------------------------------------------------------------------
# 정상 통과
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "my-bucket",
        "data2025",
        "team-photos-v2",
        "abc",  # 최소 길이 (3자)
        "a" * 63,  # 최대 길이
        "x1y",
        "log-2025-01",
    ],
)
def test_validate_bucket_name_accepts_valid(name):
    validate_bucket_name(name)  # raises 없음


# ---------------------------------------------------------------------------
# 형식 위반
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,reason_keyword",
    [
        ("ab", "3자 이상"),
        ("a" * 64, "63자 이하"),
        ("MyBucket", "소문자"),
        ("a.b", "점"),
        ("my_bucket", "밑줄"),
        ("my bucket", "공백"),
        ("my!bucket", "사용할 수 없"),
        ("foo-", "하이픈(-)으로 끝"),
        ("a--b", "연속된 하이픈"),
        ("192.168.1.1", "점"),  # 점이 먼저 차단되지만 IP 도 별도 검사
        ("1.2.3.4", "점"),
    ],
)
def test_validate_bucket_name_rejects_format(name, reason_keyword):
    with pytest.raises(ValueError) as exc_info:
        validate_bucket_name(name)
    assert reason_keyword in str(exc_info.value), (
        f"'{name}' 의 에러 메시지에 '{reason_keyword}' 가 포함되어야 함: {exc_info.value}"
    )


def test_validate_bucket_name_rejects_dot_start():
    with pytest.raises(ValueError, match="점"):
        validate_bucket_name(".hidden")


def test_validate_bucket_name_rejects_hyphen_start():
    with pytest.raises(ValueError, match="하이픈"):
        validate_bucket_name("-leading")


def test_validate_bucket_name_rejects_ipv4_format():
    """IP 주소 형식은 명시적으로 차단 (점이 먼저 차단되기는 하나 문서상 명시)."""
    # 점이 없는 IPv4-like 는 검증 통과해야 함 (그냥 숫자 이름)
    validate_bucket_name("192-168-1-1")


# ---------------------------------------------------------------------------
# 정확한 예약어 (case-insensitive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "admin",
        "Admin",
        "ADMIN",
        "administrator",
        "root",
        "system",
        "default",
        "swift",
        "ceph",
        "rgw",
        "s3",
        "aws",
        "bucket",
        "container",
        "account",
        "test-quarantine",
    ],
)
def test_validate_bucket_name_rejects_reserved_exact(name):
    with pytest.raises(ValueError, match="예약"):
        validate_bucket_name(name)


def test_validate_bucket_name_rejects_well_known():
    """'.well-known' 는 점으로 시작하므로 점 검사가 먼저 차단."""
    with pytest.raises(ValueError, match="점"):
        validate_bucket_name(".well-known")


# ---------------------------------------------------------------------------
# Suffix 위반
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "foo-quarantine",
        "data-quarantine",
        "x-quarantine",
        "team_segments",
        "abc_segments",
    ],
)
def test_validate_bucket_name_rejects_reserved_suffix(name):
    """suffix 위반은 형식 검사보다 먼저 — 단, '_segments' 는 밑줄 포함이라 형식 검사도 걸린다."""
    with pytest.raises(ValueError):
        validate_bucket_name(name)


# ---------------------------------------------------------------------------
# Prefix 위반
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "aws-data",
        "amazon-x",
        "aws-test-bucket",
    ],
)
def test_validate_bucket_name_rejects_reserved_prefix(name):
    with pytest.raises(ValueError, match="시작하는"):
        validate_bucket_name(name)


def test_validate_bucket_name_rejects_account_underscore_prefix():
    """'_account' 접두사는 밑줄이라 형식 검사로도 걸리지만 prefix 가 더 친절한 메시지."""
    with pytest.raises(ValueError):
        validate_bucket_name("_account_x")


# ---------------------------------------------------------------------------
# 입력 검사
# ---------------------------------------------------------------------------


def test_validate_bucket_name_rejects_non_string():
    with pytest.raises(ValueError, match="문자열"):
        validate_bucket_name(123)  # type: ignore[arg-type]


def test_validate_bucket_name_rejects_leading_trailing_whitespace():
    with pytest.raises(ValueError, match="공백"):
        validate_bucket_name(" my-bucket ")
