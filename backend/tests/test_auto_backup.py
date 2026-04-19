"""볼륨 자동 백업 서비스 단위 테스트."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auto_backup import (
    _is_auto_backup,
    _make_backup_name,
    disable_auto_backup,
    enable_auto_backup,
    get_auto_backup_config,
    list_auto_backup_configs,
    run_backup_cycle,
)


# ────────── 헬퍼 ──────────

def _make_backup(volume_id: str, tier: str, days_ago: int, bid: str = "bk-1") -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "id": bid,
        "name": f"auto_{volume_id[:8]}_{tier}_20240101",
        "volume_id": volume_id,
        "status": "available",
        "created_at": ts,
    }


# ────────── 이름 / 분류 헬퍼 테스트 ──────────

def test_make_backup_name_format():
    name = _make_backup_name("abc123def456", "daily")
    assert name.startswith("auto_abc123de_daily_")


def test_is_auto_backup_positive():
    b = {"name": "auto_abc123de_daily_20240101"}
    assert _is_auto_backup(b, "abc123def456", "daily")


def test_is_auto_backup_negative_tier():
    b = {"name": "auto_abc123de_weekly_20240101"}
    assert not _is_auto_backup(b, "abc123def456", "daily")


def test_is_auto_backup_negative_manual():
    b = {"name": "manual-backup"}
    assert not _is_auto_backup(b, "abc123def456", "daily")


# ────────── Redis CRUD 테스트 ──────────

@pytest.mark.asyncio
async def test_enable_and_get_config():
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)

    with patch("app.services.auto_backup._get_redis", return_value=AsyncMock(return_value=fake_redis)):
        # get_auto_backup_config은 직접 Redis를 사용
        pass

    # enable_auto_backup이 올바른 키에 저장하는지
    import json
    stored = {}

    async def fake_set(key, val):
        stored[key] = val

    async def fake_sadd(key, val):
        pass

    mock_r = AsyncMock()
    mock_r.set = fake_set
    mock_r.sadd = fake_sadd

    with patch("app.services.auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        config = await enable_auto_backup("proj-1", "vol-1", max_daily=2, max_weekly=2, max_monthly=1)

    assert config["volume_id"] == "vol-1"
    assert config["project_id"] == "proj-1"
    assert config["max_daily"] == 2
    expected_key = "afterglow:auto_backup:config:proj-1:vol-1"
    assert expected_key in stored


@pytest.mark.asyncio
async def test_get_config_returns_none_when_missing():
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)

    with patch("app.services.auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        result = await get_auto_backup_config("proj-1", "vol-missing")

    assert result is None


@pytest.mark.asyncio
async def test_disable_removes_from_redis():
    mock_r = AsyncMock()
    mock_r.delete = AsyncMock()
    mock_r.srem = AsyncMock()

    with patch("app.services.auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        await disable_auto_backup("proj-1", "vol-1")

    mock_r.delete.assert_called_once_with("afterglow:auto_backup:config:proj-1:vol-1")
    mock_r.srem.assert_called_once_with("afterglow:auto_backup:all_configs", "proj-1:vol-1")


# ────────── run_backup_cycle 보존 정책 테스트 ──────────

@pytest.mark.asyncio
async def test_run_backup_cycle_creates_when_no_existing():
    """백업이 없으면 daily/weekly/monthly 모두 생성해야 한다."""
    conn = MagicMock()
    project_id = "proj-1"
    volume_id = "vol-111111"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    with patch("app.services.auto_backup.cinder") as mock_cinder:
        mock_cinder.list_backups = MagicMock(return_value=[])
        mock_cinder.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_cinder.delete_backup = MagicMock()

        await run_backup_cycle(conn, project_id, volume_id, config)

    # daily, weekly, monthly 각 1번씩 총 3번 생성
    assert mock_cinder.create_backup.call_count == 3


@pytest.mark.asyncio
async def test_run_backup_cycle_skips_when_recent():
    """최근(1시간 전) daily 백업이 있으면 신규 생성 안 함."""
    conn = MagicMock()
    volume_id = "vol-222222"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    recent_daily = _make_backup(volume_id, "daily", days_ago=0, bid="bk-recent")
    # created_at을 1시간 전으로 설정
    recent_daily["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    with patch("app.services.auto_backup.cinder") as mock_cinder:
        mock_cinder.list_backups = MagicMock(return_value=[recent_daily])
        mock_cinder.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_cinder.delete_backup = MagicMock()

        await run_backup_cycle(conn, "proj-1", volume_id, config)

    # daily는 스킵, weekly/monthly는 생성 (2번)
    assert mock_cinder.create_backup.call_count == 2


@pytest.mark.asyncio
async def test_run_backup_cycle_prunes_excess():
    """보존 개수 초과 시 오래된 백업을 삭제해야 한다."""
    conn = MagicMock()
    volume_id = "vol-333333"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    # daily 백업 3개 (max=2이므로 1개 삭제 필요)
    old_daily_1 = _make_backup(volume_id, "daily", days_ago=5, bid="bk-old-1")
    old_daily_2 = _make_backup(volume_id, "daily", days_ago=4, bid="bk-old-2")
    old_daily_3 = _make_backup(volume_id, "daily", days_ago=3, bid="bk-old-3")

    with patch("app.services.auto_backup.cinder") as mock_cinder:
        mock_cinder.list_backups = MagicMock(return_value=[old_daily_1, old_daily_2, old_daily_3])
        mock_cinder.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_cinder.delete_backup = MagicMock()

        await run_backup_cycle(conn, "proj-1", volume_id, config)

    # 가장 오래된 bk-old-1이 삭제되어야 함
    deleted_ids = [call.args[1] for call in mock_cinder.delete_backup.call_args_list]
    assert "bk-old-1" in deleted_ids


@pytest.mark.asyncio
async def test_run_backup_cycle_list_failure_does_not_raise():
    """백업 목록 조회 실패 시 예외를 밖으로 내보내지 않아야 한다."""
    conn = MagicMock()
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    with patch("app.services.auto_backup.cinder") as mock_cinder:
        mock_cinder.list_backups = MagicMock(side_effect=Exception("OpenStack error"))
        # 예외 없이 종료되어야 함
        await run_backup_cycle(conn, "proj-1", "vol-1", config)
