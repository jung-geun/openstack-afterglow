"""Regression tests for destructive DB-test target protection."""

from __future__ import annotations

import pytest

from tests.db_target_safety import (
    UnsafeDatabaseTargetError,
    assert_isolated_test_database,
    database_name,
)


def test_database_name_ignores_host_and_port() -> None:
    assert database_name("mysql+aiomysql://afterglow:dev@mariadb:3306/afterglow_test") == ("afterglow_test")
    assert database_name("mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test") == ("afterglow_test")


def test_db_tests_reject_configured_application_schema() -> None:
    with pytest.raises(UnsafeDatabaseTargetError, match="configured application database"):
        assert_isolated_test_database(
            test_database_url="mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test",
            application_database_url="mysql+aiomysql://afterglow:dev@mariadb:3306/afterglow_test",
            allow_shared=False,
        )


def test_db_tests_allow_an_isolated_schema() -> None:
    assert_isolated_test_database(
        test_database_url="mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_pytest",
        application_database_url="mysql+aiomysql://afterglow:dev@mariadb:3306/afterglow_test",
        allow_shared=False,
    )


def test_ephemeral_ci_can_explicitly_allow_a_shared_schema_name() -> None:
    assert_isolated_test_database(
        test_database_url="mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test",
        application_database_url="mysql+aiomysql://afterglow:dev@mariadb:3306/afterglow_test",
        allow_shared=True,
    )
