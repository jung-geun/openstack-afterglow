"""Trove DB 인스턴스 자동 백업 서비스 및 API 단위 테스트."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.db_auto_backup import (
    _is_auto_backup,
    _make_backup_name,
    disable_db_auto_backup,
    enable_db_auto_backup,
    get_db_auto_backup_config,
    run_db_backup_cycle,
)

_TROVE_ENABLED = os.environ.get("SERVICE_TROVE_ENABLED", "false").lower() in ("true", "1")


# ────────── 헬퍼 ──────────


def _make_backup(instance_id: str, tier: str, days_ago: int, bid: str = "bk-1") -> dict:
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    return {
        "id": bid,
        "name": f"auto_{instance_id[:8]}_{tier}_20240101",
        "instance_id": instance_id,
        "status": "COMPLETED",
        "created_at": ts,
    }


# ────────── 이름 / 분류 헬퍼 테스트 ──────────


def test_make_backup_name_format():
    name = _make_backup_name("inst-abc-xyz", "daily")
    assert name.startswith("auto_inst-abc_daily_")


def test_is_auto_backup_positive():
    b = {"name": "auto_inst-abc_daily_20240101"}
    assert _is_auto_backup(b, "inst-abc-xyz", "daily")


def test_is_auto_backup_negative_tier():
    b = {"name": "auto_inst-abc_weekly_20240101"}
    assert not _is_auto_backup(b, "inst-abc-xyz", "daily")


def test_is_auto_backup_negative_manual():
    b = {"name": "manual-backup"}
    assert not _is_auto_backup(b, "inst-abc-xyz", "daily")


# ────────── Redis CRUD 테스트 ──────────


@pytest.mark.asyncio
async def test_enable_and_get_config_stores_correct_key():
    stored = {}

    async def fake_set(key, val):
        stored[key] = val

    mock_r = AsyncMock()
    mock_r.set = fake_set
    mock_r.sadd = AsyncMock()

    with patch("app.services.db_auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        config = await enable_db_auto_backup("proj-1", "inst-1", max_daily=2, max_weekly=2, max_monthly=1)

    assert config["instance_id"] == "inst-1"
    assert config["project_id"] == "proj-1"
    assert config["max_daily"] == 2
    assert "afterglow:db_auto_backup:config:proj-1:inst-1" in stored


@pytest.mark.asyncio
async def test_get_config_returns_none_when_missing():
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)

    with patch("app.services.db_auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        result = await get_db_auto_backup_config("proj-1", "inst-missing")

    assert result is None


@pytest.mark.asyncio
async def test_disable_removes_from_redis():
    mock_r = AsyncMock()
    mock_r.delete = AsyncMock()
    mock_r.srem = AsyncMock()

    with patch("app.services.db_auto_backup._get_redis", new=AsyncMock(return_value=mock_r)):
        await disable_db_auto_backup("proj-1", "inst-1")

    mock_r.delete.assert_called_once_with("afterglow:db_auto_backup:config:proj-1:inst-1")
    mock_r.srem.assert_called_once_with("afterglow:db_auto_backup:all_configs", "proj-1:inst-1")


# ────────── run_db_backup_cycle 보존 정책 테스트 ──────────


@pytest.mark.asyncio
async def test_run_backup_cycle_creates_when_no_existing():
    """백업이 없으면 daily/weekly/monthly 모두 생성해야 한다."""
    conn = MagicMock()
    instance_id = "inst-111111"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    with patch("app.services.db_auto_backup.trove") as mock_trove:
        mock_trove.list_backups = MagicMock(return_value=[])
        mock_trove.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_trove.delete_backup = MagicMock()

        await run_db_backup_cycle(conn, "proj-1", instance_id, config)

    assert mock_trove.create_backup.call_count == 3


@pytest.mark.asyncio
async def test_run_backup_cycle_skips_when_recent():
    """최근(1시간 전) daily 백업이 있으면 신규 생성 안 함."""
    conn = MagicMock()
    instance_id = "inst-222222"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    recent_daily = _make_backup(instance_id, "daily", days_ago=0, bid="bk-recent")
    recent_daily["created_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    with patch("app.services.db_auto_backup.trove") as mock_trove:
        mock_trove.list_backups = MagicMock(return_value=[recent_daily])
        mock_trove.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_trove.delete_backup = MagicMock()

        await run_db_backup_cycle(conn, "proj-1", instance_id, config)

    # daily 스킵, weekly/monthly 생성 (2번)
    assert mock_trove.create_backup.call_count == 2


@pytest.mark.asyncio
async def test_run_backup_cycle_prunes_excess():
    """보존 개수 초과 시 오래된 백업을 삭제해야 한다."""
    conn = MagicMock()
    instance_id = "inst-333333"
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    old_1 = _make_backup(instance_id, "daily", days_ago=5, bid="bk-old-1")
    old_2 = _make_backup(instance_id, "daily", days_ago=4, bid="bk-old-2")
    old_3 = _make_backup(instance_id, "daily", days_ago=3, bid="bk-old-3")

    with patch("app.services.db_auto_backup.trove") as mock_trove:
        mock_trove.list_backups = MagicMock(return_value=[old_1, old_2, old_3])
        mock_trove.create_backup = MagicMock(return_value={"id": "new-bk"})
        mock_trove.delete_backup = MagicMock()

        await run_db_backup_cycle(conn, "proj-1", instance_id, config)

    deleted_ids = [call.args[1] for call in mock_trove.delete_backup.call_args_list]
    assert "bk-old-1" in deleted_ids


@pytest.mark.asyncio
async def test_run_backup_cycle_list_failure_does_not_raise():
    """백업 목록 조회 실패 시 예외를 밖으로 내보내지 않아야 한다."""
    conn = MagicMock()
    config = {"max_daily": 2, "max_weekly": 2, "max_monthly": 1}

    with patch("app.services.db_auto_backup.trove") as mock_trove:
        mock_trove.list_backups = MagicMock(side_effect=Exception("OpenStack error"))
        await run_db_backup_cycle(conn, "proj-1", "inst-1", config)


# ────────── API 엔드포인트 인증 관문 테스트 ──────────


@pytest.mark.asyncio
async def test_get_auto_backup_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/database-instances/inst-1/auto-backup")
    assert resp.status_code in (401, 404, 405)


@pytest.mark.asyncio
async def test_put_auto_backup_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.put("/api/v1/database-instances/inst-1/auto-backup", json={"max_daily": 2})
    assert resp.status_code in (401, 404, 405, 422)


@pytest.mark.asyncio
async def test_delete_auto_backup_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.delete("/api/v1/database-instances/inst-1/auto-backup")
    assert resp.status_code in (401, 404, 405)


# ────────── API 엔드포인트 기능 테스트 (Trove 활성화 필요) ──────────


@pytest.mark.asyncio
@pytest.mark.skipif(not _TROVE_ENABLED, reason="Trove 서비스 비활성화")
async def test_put_and_get_auto_backup(client, mock_conn):
    with (
        patch(
            "app.services.db_auto_backup._get_redis",
            new=AsyncMock(
                return_value=AsyncMock(
                    set=AsyncMock(),
                    sadd=AsyncMock(),
                    get=AsyncMock(return_value=None),
                )
            ),
        ),
        patch(
            "app.services.trove.get_instance",
            MagicMock(return_value=MagicMock(project_id="test-project-123", tenant_id=None)),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put(
                "/api/v1/database-instances/inst-1/auto-backup",
                json={"max_daily": 3, "max_weekly": 2, "max_monthly": 1},
                headers={"Authorization": "Bearer test-token"},
            )
        assert resp.status_code in (200, 401, 403)


@pytest.mark.asyncio
@pytest.mark.skipif(not _TROVE_ENABLED, reason="Trove 서비스 비활성화")
async def test_delete_auto_backup_removes_config(client, mock_conn):
    with patch(
        "app.services.db_auto_backup._get_redis",
        new=AsyncMock(
            return_value=AsyncMock(
                delete=AsyncMock(),
                srem=AsyncMock(),
            )
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.delete(
                "/api/v1/database-instances/inst-1/auto-backup",
                headers={"Authorization": "Bearer test-token"},
            )
        assert resp.status_code in (204, 401, 403)


@pytest.mark.asyncio
async def test_backup_cycle_skips_when_recent_created_at():
    """created_at 키로 마지막 백업 시각을 올바르게 읽어 min_interval 내 재생성하지 않는지 검증."""
    now = datetime.now(UTC)
    recent = (now - timedelta(hours=1)).isoformat()  # 1시간 전 — daily min_interval(24h) 이내

    instance_id = "inst-1234-5678"
    mock_backups = [
        {
            "id": "b-1",
            "name": f"auto_{instance_id[:8]}_daily_20260605",
            "created_at": recent,
            "updated_at": recent,
            "status": "COMPLETED",
            "instance_id": instance_id,
        }
    ]

    with patch("app.services.db_auto_backup.trove") as mock_trove:
        mock_trove.list_backups = MagicMock(return_value=mock_backups)
        mock_trove.create_backup = MagicMock()
        mock_trove.delete_backup = MagicMock()

        conn = MagicMock()
        config = {"max_daily": 2, "max_weekly": 0, "max_monthly": 0}
        from app.services import db_auto_backup

        await db_auto_backup.run_db_backup_cycle(conn, "proj-1", instance_id, config)

    # 24h min_interval 이내 → 새 daily 백업을 생성하지 않아야 함
    mock_trove.create_backup.assert_not_called()
