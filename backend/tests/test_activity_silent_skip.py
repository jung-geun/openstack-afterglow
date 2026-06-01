"""Phase 51c — ActivityLog db 미연결 시 rate-limited warning 테스트."""

import time as time_mod
from unittest.mock import patch

import pytest

import app.services.activity as act_mod
from app.services.activity import record


@pytest.mark.asyncio
async def test_record_skips_and_warns_when_db_unavailable():
    """is_db_available() False 시 ActivityLog 기록 skip + warning 로그 1회."""
    act_mod._last_db_warn_ts = 0.0

    with patch.object(act_mod.logger, "warning") as mock_warn:
        with patch("app.services.activity.is_db_available", return_value=False):
            await record(
                project_id="p1",
                user_id="u1",
                username="tester",
                resource_type="instance",
                action="instance.create",
                status="success",
            )

    mock_warn.assert_called_once()
    msg = mock_warn.call_args[0][0]
    assert "db unavailable" in msg.lower() or "ActivityLog skipped" in msg


@pytest.mark.asyncio
async def test_record_rate_limits_warnings():
    """60초 이내 반복 호출 시 warning 1회만 emit."""
    act_mod._last_db_warn_ts = 0.0

    async def _call():
        await record(
            project_id="p1",
            user_id="u1",
            username="t",
            resource_type="instance",
            action="instance.create",
            status="success",
        )

    with patch.object(act_mod.logger, "warning") as mock_warn:
        with patch("app.services.activity.is_db_available", return_value=False):
            await _call()
            act_mod._last_db_warn_ts = time_mod.monotonic()
            await _call()
            await _call()

    assert mock_warn.call_count == 1


@pytest.mark.asyncio
async def test_record_does_not_raise_when_db_unavailable():
    """DB 미연결 시 예외 미발생 — best-effort 보장."""
    act_mod._last_db_warn_ts = 0.0

    with patch("app.services.activity.is_db_available", return_value=False):
        await record(
            project_id="p1",
            user_id="u1",
            username="t",
            resource_type="instance",
            action="instance.delete",
            status="success",
        )
