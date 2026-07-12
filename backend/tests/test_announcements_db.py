"""announcements 서비스 — MariaDB 실 SQL 통합 테스트.

타겟팅(all/project/user) 판별, IDOR(타 유저 대상 공지 read-mark 차단), 읽음 상태
영속성은 SQLAlchemy where절의 실제 SQL 평가에 의존하므로 mock 우회 없이 실 DB로
검증한다 (tests/test_union_layers_db.py 패턴 준용).

실행: AFTERGLOW_TEST_DATABASE_URL=mysql+aiomysql://afterglow:dev@127.0.0.1:3306/afterglow_test \
     pytest tests/test_announcements_db.py -v -m db
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models.db  # noqa: F401 — side-effect: Base에 ORM 모델 등록
from app import database as db_mod
from app.services import announcements as svc
from app.services.announcements import AnnouncementNotFoundError

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_DB_URL_ENV = "AFTERGLOW_TEST_DATABASE_URL"


def _make(**overrides):
    defaults: dict = dict(
        title="공지 제목",
        body="공지 본문",
        severity="info",
        target_type="all",
        target_id=None,
        starts_at=None,
        ends_at=None,
        created_by_user_id="admin-1",
        created_by_username="admin",
    )
    defaults.update(overrides)
    return svc.create_announcement(**defaults)


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
async def live_db(db_tables, db_url):
    """announcements 서비스가 참조하는 전역 세션 팩토리를 실 DB에 바인딩."""
    db_mod.init_db(db_url)
    yield
    factory = db_mod.get_session_factory()
    async with factory() as session:
        await session.execute(text("DELETE FROM announcement_reads"))
        await session.execute(text("DELETE FROM announcements"))
        await session.commit()
    await db_mod.close_db()


async def test_all_target_visible_to_any_authenticated_user(live_db):
    created = await _make(target_type="all")

    visible = await svc.list_user_announcements(user_id="user-x", project_id="project-x")

    assert [a["id"] for a in visible] == [created["id"]]
    assert visible[0]["is_read"] is False


async def test_project_target_only_visible_to_matching_project(live_db):
    created = await _make(severity="warning", target_type="project", target_id="project-a")

    visible_match = await svc.list_user_announcements(user_id="user-x", project_id="project-a")
    visible_other = await svc.list_user_announcements(user_id="user-x", project_id="project-b")

    assert [a["id"] for a in visible_match] == [created["id"]]
    assert visible_other == []


async def test_user_target_only_visible_to_matching_user(live_db):
    created = await _make(severity="danger", target_type="user", target_id="user-a")

    visible_match = await svc.list_user_announcements(user_id="user-a", project_id="any-project")
    visible_other = await svc.list_user_announcements(user_id="user-b", project_id="any-project")

    assert [a["id"] for a in visible_match] == [created["id"]]
    assert visible_other == []


async def test_mark_read_by_unauthorized_user_is_rejected_and_leaves_no_trace(live_db):
    """IDOR 회귀: user-a 대상 공지를 user-b가 읽음 처리하려 하면 False (라우터는 404 매핑)."""
    created = await _make(target_type="user", target_id="user-a")

    ok_wrong_user = await svc.mark_read(announcement_id=created["id"], user_id="user-b", project_id="irrelevant")
    assert ok_wrong_user is False

    # 다른 유저의 시도가 실제 읽음 레코드를 만들지 않았는지 소유자 관점에서 재확인
    unread_for_owner = await svc.count_unread(user_id="user-a", project_id="irrelevant")
    assert unread_for_owner == 1

    ok_owner = await svc.mark_read(announcement_id=created["id"], user_id="user-a", project_id="irrelevant")
    assert ok_owner is True
    assert await svc.count_unread(user_id="user-a", project_id="irrelevant") == 0


async def test_mark_read_for_unknown_announcement_returns_false(live_db):
    ok = await svc.mark_read(announcement_id=999_999, user_id="user-a", project_id="p")
    assert ok is False


async def test_unread_count_and_read_state_are_per_user(live_db):
    a1 = await _make(title="A")
    a2 = await _make(title="B")

    assert await svc.count_unread(user_id="u1", project_id="p1") == 2

    await svc.mark_read(announcement_id=a1["id"], user_id="u1", project_id="p1")
    assert await svc.count_unread(user_id="u1", project_id="p1") == 1

    # 읽음 상태는 유저별로 독립 — u2는 여전히 2건 미읽음
    assert await svc.count_unread(user_id="u2", project_id="p1") == 2
    _ = a2  # noqa: F841 — 두 건 존재 확인용으로만 생성


async def test_inactive_announcement_is_hidden_from_users_but_kept_in_admin_list(live_db):
    created = await _make(title="비활성 예정")
    await svc.update_announcement(created["id"], is_active=False)

    visible = await svc.list_user_announcements(user_id="anyone", project_id="anyone")
    assert visible == []

    admin_list = await svc.list_admin_announcements()
    match = next(a for a in admin_list if a["id"] == created["id"])
    assert match["is_active"] is False


async def test_future_scheduled_announcement_not_yet_visible(live_db):
    future = datetime.now(UTC) + timedelta(days=1)
    await _make(title="예약 공지", starts_at=future)

    visible = await svc.list_user_announcements(user_id="anyone", project_id="anyone")
    assert visible == []


async def test_expired_announcement_no_longer_visible(live_db):
    past = datetime.now(UTC) - timedelta(days=1)
    await _make(title="만료 공지", ends_at=past)

    visible = await svc.list_user_announcements(user_id="anyone", project_id="anyone")
    assert visible == []


async def test_update_announcement_persists_changes(live_db):
    created = await _make(title="원본", severity="info")

    updated = await svc.update_announcement(created["id"], title="수정됨", severity="warning")

    assert updated["title"] == "수정됨"
    assert updated["severity"] == "warning"


async def test_delete_announcement_removes_it_from_admin_list(live_db):
    created = await _make(title="삭제될 공지")

    await svc.delete_announcement(created["id"])

    admin_list = await svc.list_admin_announcements()
    assert all(a["id"] != created["id"] for a in admin_list)


async def test_update_nonexistent_announcement_raises_not_found(live_db):
    with pytest.raises(AnnouncementNotFoundError):
        await svc.update_announcement(999_999, title="x")


async def test_delete_nonexistent_announcement_raises_not_found(live_db):
    with pytest.raises(AnnouncementNotFoundError):
        await svc.delete_announcement(999_999)
