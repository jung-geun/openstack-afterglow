"""Deployment schema bootstrap contract tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app import bootstrap


def _settings(database_url: str = "mysql+aiomysql://user:pass@db/afterglow"):
    return SimpleNamespace(
        database_url=database_url,
        database_pool_size=7,
        database_max_overflow=3,
        database_connect_timeout=20,
        database_pool_timeout=30,
        database_unhealthy_seconds=45,
    )


async def test_bootstrap_initializes_schema_with_configured_database_options():
    init_db = patch("app.bootstrap.init_db").start()
    create_tables = patch("app.bootstrap.create_tables", new_callable=AsyncMock).start()
    close_db = patch("app.bootstrap.close_db", new_callable=AsyncMock).start()
    get_settings = patch("app.bootstrap.get_settings", return_value=_settings()).start()
    try:
        await bootstrap.main()
    finally:
        patch.stopall()

    get_settings.assert_called_once_with()
    init_db.assert_called_once_with(
        "mysql+aiomysql://user:pass@db/afterglow",
        pool_size=7,
        max_overflow=3,
        connect_timeout=20,
        pool_timeout=30,
        unhealthy_seconds=45,
    )
    create_tables.assert_awaited_once_with()
    close_db.assert_awaited_once_with()


async def test_bootstrap_rejects_missing_database_url_and_closes_database():
    init_db = patch("app.bootstrap.init_db").start()
    create_tables = patch("app.bootstrap.create_tables", new_callable=AsyncMock).start()
    close_db = patch("app.bootstrap.close_db", new_callable=AsyncMock).start()
    patch("app.bootstrap.get_settings", return_value=_settings("")).start()
    try:
        with pytest.raises(RuntimeError, match="database_url must be configured"):
            await bootstrap.main()
    finally:
        patch.stopall()

    init_db.assert_not_called()
    create_tables.assert_not_awaited()
    close_db.assert_awaited_once_with()


async def test_bootstrap_propagates_schema_failure_after_closing_database():
    schema_error = RuntimeError("schema creation failed")
    init_db = patch("app.bootstrap.init_db").start()
    create_tables = patch("app.bootstrap.create_tables", new_callable=AsyncMock, side_effect=schema_error).start()
    close_db = patch("app.bootstrap.close_db", new_callable=AsyncMock).start()
    patch("app.bootstrap.get_settings", return_value=_settings()).start()
    try:
        with pytest.raises(RuntimeError, match="schema creation failed"):
            await bootstrap.main()
    finally:
        patch.stopall()

    init_db.assert_called_once()
    create_tables.assert_awaited_once_with()
    close_db.assert_awaited_once_with()
