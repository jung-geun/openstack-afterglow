"""Phase 51c — ActivityLog db 미연결 시 rate-limited warning 테스트."""

import logging
import time as time_mod
from unittest.mock import patch

import pytest

from app.services.activity import record


@pytest.mark.asyncio
async def test_record_skips_and_warns_when_db_unavailable(caplog):
    """is_db_available() False 시 ActivityLog 기록 skip + warning 로그 1회."""
    import app.services.activity as act_mod

    act_mod._last_db_warn_ts = 0.0

    caplog.set_level(logging.WARNING, logger="app.services.activity")
    with patch("app.services.activity.is_db_available", return_value=False):
        await record(
            project_id="p1",
            user_id="u1",
            username="tester",
            resource_type="instance",
            action="instance.create",
            status="success",
        )

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "db unavailable" in msg.lower() or "ActivityLog skipped" in msg


@pytest.mark.asyncio
async def test_record_rate_limits_warnings(caplog):
    """60초 이내 반복 호출 시 warning 1회만 emit."""
    import app.services.activity as act_mod

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

    caplog.set_level(logging.WARNING, logger="app.services.activity")
    with patch("app.services.activity.is_db_available", return_value=False):
        await _call()
        # rate limit 시뮬레이션: _last_db_warn_ts를 현재로 업데이트하여 60초 이내 간주
        act_mod._last_db_warn_ts = time_mod.monotonic()
        await _call()
        await _call()

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_record_does_not_raise_when_db_unavailable():
    """DB 미연결 시 예외 미발생 — best-effort 보장."""
    import app.services.activity as act_mod

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
