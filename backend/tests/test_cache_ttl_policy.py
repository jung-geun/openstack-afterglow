"""Phase B: TTL 카테고리 + jitter + dynamic 조정 테스트."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# jittered() 분포 검증
# ---------------------------------------------------------------------------


def test_jittered_within_bounds():
    from app.services.cache.ttl import jittered

    base = 100
    for _ in range(1000):
        result = jittered(base)
        assert 85 <= result <= 115, f"jitter 범위 초과: {result}"


def test_jittered_not_always_same():
    from app.services.cache.ttl import jittered

    results = {jittered(100) for _ in range(50)}
    assert len(results) > 1, "jitter 가 적용되지 않음 (항상 같은 값)"


# ---------------------------------------------------------------------------
# dynamic_adjust() 임계치 동작
# ---------------------------------------------------------------------------


def test_dynamic_adjust_below_low(settings_override):
    from app.services.cache.ttl import dynamic_adjust

    assert dynamic_adjust(300, mutcount=0) == 300
    assert dynamic_adjust(300, mutcount=4) == 300


def test_dynamic_adjust_between_thresholds(settings_override):
    from app.services.cache.ttl import dynamic_adjust

    result = dynamic_adjust(300, mutcount=5)
    assert result == max(150, 30)  # 300 × 0.5 = 150

    result = dynamic_adjust(300, mutcount=19)
    assert result == 150


def test_dynamic_adjust_above_high(settings_override):
    from app.services.cache.ttl import dynamic_adjust

    result = dynamic_adjust(900, mutcount=20)
    assert result == 30  # operational_live 강제

    result = dynamic_adjust(86400, mutcount=100)
    assert result == 30


def test_dynamic_adjust_small_base_stays_at_floor(settings_override):
    from app.services.cache.ttl import dynamic_adjust

    # base=30 이면 ×0.5 = 15 이나 floor=30 → 30 유지
    result = dynamic_adjust(30, mutcount=10)
    assert result == 30


# ---------------------------------------------------------------------------
# 카테고리 기본값 확인
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,expected_min,expected_max",
    [
        ("identity_stable", 73440, 99360),  # 86400 ±15%
        ("catalog_slow", 765, 1036),  # 900 ±15%
        ("project_meta", 255, 346),  # 300 ±15%
        ("operational_live", 25, 35),  # 30 ±15%
        ("admin_overview", 51, 70),  # 60 ±15%
    ],
)
def test_category_base_ttl_range(category, expected_min, expected_max):
    from app.services.cache.ttl import _base_for_category, jittered

    base = _base_for_category(category)
    for _ in range(200):
        result = jittered(base)
        assert expected_min <= result <= expected_max, (
            f"category={category} base={base} jittered={result} 범위 [{expected_min}, {expected_max}] 초과"
        )


# ---------------------------------------------------------------------------
# for_category() async 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_for_category_identity_stable():
    from app.services.cache.ttl import for_category

    # identity_stable 은 dynamic 조정 없이 jitter 만 적용
    ttl = await for_category("identity_stable")
    assert 73440 <= ttl <= 99360  # 86400 ±15%


@pytest.mark.asyncio
async def test_for_category_operational_live_no_service():
    from app.services.cache.ttl import for_category

    # service/project_id 없으면 mutcount 조회 안 함 → 기본 jitter 만
    ttl = await for_category("operational_live")
    assert 25 <= ttl <= 35


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def settings_override(monkeypatch):
    """테스트용: 기본 threshold 값 적용."""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "cache_dynamic_threshold_low", 5)
    monkeypatch.setattr(s, "cache_dynamic_threshold_high", 20)
    yield s
