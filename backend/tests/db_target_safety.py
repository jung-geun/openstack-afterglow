"""Safety checks for destructive database-marked tests."""

from __future__ import annotations

from sqlalchemy.engine import make_url


class UnsafeDatabaseTargetError(ValueError):
    """Raised when DB tests target the application's active schema."""


def database_name(database_url: str) -> str | None:
    """Return a normalized database name from a SQLAlchemy URL."""
    database = make_url(database_url).database
    return database.casefold() if database else None


def assert_isolated_test_database(*, test_database_url: str, application_database_url: str, allow_shared: bool) -> None:
    """Reject a DB-test target that shares the configured application schema."""
    if allow_shared or not application_database_url:
        return

    test_database = database_name(test_database_url)
    application_database = database_name(application_database_url)
    if test_database and test_database == application_database:
        raise UnsafeDatabaseTargetError(
            "DB tests target the configured application database "
            f"{test_database!r}. Set AFTERGLOW_TEST_DATABASE_URL to an isolated "
            "schema, or set AFTERGLOW_ALLOW_SHARED_TEST_DATABASE=1 only for an "
            "ephemeral CI database."
        )
