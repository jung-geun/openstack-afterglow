"""VM cloud-init library service — MariaDB encrypted persistence integration tests.

Run with AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://... pytest -m db.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models.db  # noqa: F401 — registers ORM models with Base metadata
from app import database as db_mod
from app.models.db import VmCloudInitSnippet
from app.services import vm_cloud_init_library as svc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


@pytest.fixture(scope="module")
def db_tables(db_url):
    from app.database import Base

    async def setup():
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def teardown():
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(setup())
    yield
    asyncio.run(teardown())


@pytest_asyncio.fixture
async def live_db(db_tables, db_url):
    db_mod.init_db(db_url)
    yield
    factory = db_mod.get_session_factory()
    async with factory() as session:
        await session.execute(text("DELETE FROM vm_cloud_init_snippets"))
        await session.commit()
    await db_mod.close_db()


async def test_preset_round_trip_is_encrypted_and_upserts(live_db):
    first = await svc.create_preset(user_id="user-a", name="bootstrap", content="#cloud-config\npackages: [htop]")
    second = await svc.create_preset(user_id="user-a", name="bootstrap", content="#cloud-config\npackages: [curl]")

    assert first["id"] == second["id"]
    library = await svc.list_snippets("user-a")
    assert library["presets"] == [
        {
            **second,
            "content": "#cloud-config\npackages: [curl]",
        }
    ]

    factory = db_mod.get_session_factory()
    async with factory() as session:
        stored = await session.scalar(select(VmCloudInitSnippet.content_encrypted))
    assert stored is not None
    assert "packages: [curl]" not in stored


async def test_preset_is_user_scoped_and_deletable(live_db):
    preset = await svc.create_preset(user_id="user-a", name="bootstrap", content="#cloud-config\npackages: [htop]")
    assert await svc.list_snippets("user-b") == {"history": [], "presets": []}

    await svc.delete_snippet(user_id="user-a", snippet_id=preset["id"])
    assert await svc.list_snippets("user-a") == {"history": [], "presets": []}


async def test_history_retains_the_latest_twenty_entries(live_db):
    for index in range(21):
        await svc.record_history(user_id="user-a", content=f"#cloud-config\n# {index}")

    history = (await svc.list_snippets("user-a"))["history"]
    assert len(history) == 20
    assert {entry["content"] for entry in history} == {f"#cloud-config\n# {index}" for index in range(1, 21)}
