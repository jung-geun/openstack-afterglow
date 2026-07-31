from datetime import UTC, datetime

import pytest

from app.services.chat.conversation_store import _iso, _local_iso
from app.services.chat.message_timestamps import message_timestamps, validate_client_timezone


def test_message_timestamps_preserve_one_utc_instant_and_its_local_wall_clock():
    created_at, created_at_local, timezone_name = message_timestamps(
        "Asia/Seoul", now=datetime(2026, 7, 28, 12, 34, 56, 123456, tzinfo=UTC)
    )

    assert created_at == datetime(2026, 7, 28, 12, 34, 56, 123456, tzinfo=UTC)
    assert created_at_local == datetime(2026, 7, 28, 21, 34, 56, 123456)
    assert timezone_name == "Asia/Seoul"


def test_message_timestamps_keep_legacy_compatible_null_local_fields_without_timezone():
    created_at, created_at_local, timezone_name = message_timestamps(None, now=datetime(2026, 7, 28, 12, 0, tzinfo=UTC))

    assert created_at == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    assert created_at_local is None
    assert timezone_name is None


def test_message_timestamps_treat_naive_injected_clock_as_utc():
    created_at, created_at_local, timezone_name = message_timestamps(
        "America/New_York", now=datetime(2026, 7, 28, 12, 0)
    )

    assert created_at == datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    assert created_at_local == datetime(2026, 7, 28, 8, 0)
    assert timezone_name == "America/New_York"


def test_timestamp_serialization_marks_naive_database_utc_with_z_without_rewriting_local_wall_clock():
    assert _iso(datetime(2026, 7, 28, 12, 0)) == "2026-07-28T12:00:00Z"
    assert _local_iso(datetime(2026, 7, 28, 21, 0)) == "2026-07-28T21:00:00"


def test_unknown_client_timezone_is_rejected():
    with pytest.raises(ValueError, match="client_timezone"):
        validate_client_timezone("not-a-timezone")
