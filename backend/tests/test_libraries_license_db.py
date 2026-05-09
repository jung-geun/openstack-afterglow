"""라이선스/동시 마운트 가드 — MariaDB 실 SQL 검증.

11.2의 `union_layers.record_mount` 가드(`max_concurrent_mounts` 초과 시 409) 회귀 방지.
실 DB 카운트 기반이라 mock 우회 시 self-test 위험이 있어 `@pytest.mark.db`로 작성.

실행:
    AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test \
    pytest tests/test_libraries_license_db.py -v -m db
"""

import asyncio
import os
import secrets

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.db  # noqa: F401 — side-effect: Base에 ORM 모델 등록
from app.models.union import CreateLayerRequest
from app.services import union_layers as svc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"


def _hash() -> str:
    return f"sha256:{secrets.token_hex(32)}"


def _req(**kwargs) -> CreateLayerRequest:
    defaults = dict(
        name="lic-layer",
        version="1.0",
        content_hash=_hash(),
        ubuntu_base="ubuntu:22.04",
        build_recipe={},
        installed_packages={},
        size_bytes=1024,
        file_count=10,
    )
    defaults.update(kwargs)
    return CreateLayerRequest(**defaults)


@pytest.fixture(scope="module")
def db_url():
    url = os.environ.get(_DB_URL_ENV)
    if not url:
        pytest.skip(f"{_DB_URL_ENV} 미설정 — MariaDB 통합 테스트 건너뜀")
    return url


@pytest.fixture(scope="module")
def db_tables(db_url):
    from app.database import Base

    async def _setup():
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _teardown():
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_setup())
    yield
    asyncio.run(_teardown())


@pytest_asyncio.fixture
async def sess(db_tables, db_url):
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await session.execute(text("DELETE FROM union_user_mounts"))
        await session.execute(text("DELETE FROM union_templates"))
        await session.execute(text("DELETE FROM union_layers"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        await session.commit()
    await engine.dispose()


async def _create_sealed_layer(
    sess: AsyncSession,
    license_type: str | None,
    max_concurrent_mounts: int | None,
) -> str:
    """레이어 생성 + seal + 라이선스 필드 직접 SQL UPDATE → leaf_layer_id 반환.

    라이선스 필드는 빌드 파이프라인이 metadata로 채우는 값이므로 service 우회.
    """
    info = await svc.create_layer(sess, _req(), created_by="lic-test")
    sealed = await svc.seal_layer(sess, info.id)
    await sess.execute(
        text("UPDATE union_layers SET license_type = :lt, max_concurrent_mounts = :mcm WHERE id = :id"),
        {"lt": license_type, "mcm": max_concurrent_mounts, "id": sealed.id},
    )
    await sess.commit()
    return sealed.id


async def test_commercial_two_concurrent_third_blocked(sess):
    """commercial + max=2 → 첫 두 mount 성공, 세 번째 409."""
    leaf = await _create_sealed_layer(sess, "commercial", 2)

    m1 = await svc.record_mount(sess, "user1", "vm-001", leaf)
    m2 = await svc.record_mount(sess, "user2", "vm-002", leaf)
    assert m1.id != m2.id

    with pytest.raises(HTTPException) as exc:
        await svc.record_mount(sess, "user3", "vm-003", leaf)
    assert exc.value.status_code == 409
    assert "concurrent mount limit" in (exc.value.detail or "").lower()


async def test_unmount_releases_slot_for_new_mount(sess):
    """unmount 후 빈 슬롯에서 다시 mount 가능."""
    leaf = await _create_sealed_layer(sess, "commercial", 1)

    m1 = await svc.record_mount(sess, "user1", "vm-001", leaf)

    with pytest.raises(HTTPException) as exc:
        await svc.record_mount(sess, "user2", "vm-002", leaf)
    assert exc.value.status_code == 409

    await svc.record_unmount(sess, m1.id, "user1")

    # 슬롯 비었으니 새 mount 성공
    m3 = await svc.record_mount(sess, "user2", "vm-002", leaf)
    assert m3.id != m1.id
    assert m3.unmounted_at is None


async def test_open_license_unlimited(sess):
    """open + max=NULL → 동시 마운트 무제한 (10건 모두 성공)."""
    leaf = await _create_sealed_layer(sess, "open", None)

    mount_ids = []
    for i in range(10):
        m = await svc.record_mount(sess, f"user{i}", f"vm-{i:03d}", leaf)
        mount_ids.append(m.id)
    assert len(set(mount_ids)) == 10


async def test_zero_cap_blocks_all_mounts(sess):
    """max=0 → 어떤 mount도 즉시 409."""
    leaf = await _create_sealed_layer(sess, "commercial", 0)

    with pytest.raises(HTTPException) as exc:
        await svc.record_mount(sess, "user1", "vm-001", leaf)
    assert exc.value.status_code == 409
