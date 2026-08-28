"""Regression tests for the one-time runtime settings importer."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "runtime_settings_importer",
    Path(__file__).resolve().parents[1] / "scripts/import_runtime_infrastructure_settings.py",
)
assert _SPEC and _SPEC.loader
importer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(importer)


def test_parse_legacy_base_images_requires_unique_release_mapping():
    assert importer._parse_legacy_base_images(["ubuntu-24.04=img-24"]) == {"ubuntu-24.04": "img-24"}
    with pytest.raises(ValueError, match="RELEASE=IMAGE_ID"):
        importer._parse_legacy_base_images(["bad-value"])
    with pytest.raises(ValueError, match="duplicate"):
        importer._parse_legacy_base_images(["ubuntu-24.04=img-24", "ubuntu-24.04=img-other"])


def test_legacy_bool_honors_explicit_environment(monkeypatch):
    config = {"notion": {"enabled": False}}
    monkeypatch.setenv("NOTION_ENABLED", "true")
    assert importer._legacy_bool(config, "notion", "enabled", "NOTION_ENABLED") is True
    monkeypatch.setenv("NOTION_ENABLED", "not-a-bool")
    assert importer._legacy_bool(config, "notion", "enabled", "NOTION_ENABLED") is None


def test_default_availability_zone_seeds_compute_and_volume_policies():
    source = ("nova", "default_availability_zone", "DEFAULT_AVAILABILITY_ZONE")
    assert importer._POLICY_SOURCES["nova.default_compute_availability_zone"] == source
    assert importer._POLICY_SOURCES["cinder.default_volume_availability_zone"] == source


@pytest.fixture(scope="module")
def importer_database_url():
    database_url = os.environ.get("AFTERGLOW_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("AFTERGLOW_TEST_DATABASE_URL 미설정 — importer DB 통합 테스트 건너뜀")
    return database_url


@pytest.fixture(scope="module")
def importer_database(importer_database_url):
    async def setup():
        from sqlalchemy.ext.asyncio import create_async_engine

        import app.models.db  # noqa: F401
        from app.database import Base

        engine = create_async_engine(importer_database_url, pool_pre_ping=True)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def teardown():
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.database import Base

        engine = create_async_engine(importer_database_url, pool_pre_ping=True)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(setup())
    yield importer_database_url
    asyncio.run(teardown())


async def _importer_rows(database_url: str) -> tuple[dict[str, str], dict[str, object]]:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models.db import ResourcePolicy, RuntimeSetting

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            policies = {
                row.policy_key: row.resource_id for row in (await session.execute(select(ResourcePolicy))).scalars()
            }
            runtime = {
                row.setting_key: row.value_json for row in (await session.execute(select(RuntimeSetting))).scalars()
            }
            return policies, runtime
    finally:
        await engine.dispose()


async def _add_pending_library_build(database_url: str) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models.db import LibraryBuild

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                LibraryBuild(
                    library_id="library-1",
                    file_storage_id="storage-1",
                    status="pending",
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.db
def test_apply_seeds_once_and_rolls_back_on_write_failure(importer_database):
    selected = {
        "nova.default_network": {"id": "network-1", "name": "tenant-network"},
    }
    runtime = {"notion.sync_enabled": True}

    assert asyncio.run(importer._apply(importer_database, selected, runtime, {})) == (1, 1, 0)
    assert asyncio.run(_importer_rows(importer_database)) == (
        {"nova.default_network": "network-1"},
        {"notion.sync_enabled": True},
    )
    assert asyncio.run(importer._apply(importer_database, selected, runtime, {})) == (0, 0, 0)

    from sqlalchemy.exc import StatementError

    with pytest.raises(StatementError):
        asyncio.run(
            importer._apply(
                importer_database,
                {"nova.default_network": {"id": "network-1", "name": "tenant-network"}},
                {"notion.sync_enabled_rollback": object()},
                {},
            )
        )

    assert asyncio.run(_importer_rows(importer_database)) == (
        {"nova.default_network": "network-1"},
        {"notion.sync_enabled": True},
    )

    asyncio.run(_add_pending_library_build(importer_database))
    with pytest.raises(ValueError, match="unresolved in-flight resource snapshots"):
        asyncio.run(
            importer._apply(
                importer_database,
                {"nova.default_network": {"id": "network-1", "name": "tenant-network"}},
                {},
                {},
            )
        )
    assert asyncio.run(_importer_rows(importer_database)) == (
        {"nova.default_network": "network-1"},
        {"notion.sync_enabled": True},
    )
