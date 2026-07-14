"""공지(announcement) 라우터 — 인가/입력검증/DB-unavailable graceful degrade 회귀.

타겟팅 정확성·IDOR·읽음 처리 등 SQL 의존 로직은 실 DB가 필요해
tests/test_announcements_db.py(@pytest.mark.db)에서 검증한다. 이 파일은 HTTP
계층(403/400/503/graceful-empty)만 다루며 DB 없이 항상 실행된다.
"""

from __future__ import annotations

import pytest

from app.services import announcements as announcements_service


@pytest.mark.asyncio
async def test_non_admin_cannot_create_announcement(non_admin_client):
    resp = await non_admin_client.post(
        "/api/v1/admin/announcements",
        json={"title": "t", "body": "b", "severity": "info", "target_type": "all"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_list_admin_announcements(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/announcements")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_access_meta_options(non_admin_client):
    resp = await non_admin_client.get("/api/v1/admin/announcements/meta/options")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_meta_options_returns_whitelist(admin_client):
    resp = await admin_client.get("/api/v1/admin/announcements/meta/options")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["severities"]) == {"info", "warning", "danger"}
    assert set(body["target_types"]) == {"all", "project", "user"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"title": "t", "body": "b", "severity": "critical", "target_type": "all"},  # 잘못된 severity
        {"title": "t", "body": "b", "severity": "info", "target_type": "group"},  # 지원하지 않는 target_type
        {"title": "t", "body": "b", "severity": "info", "target_type": "user"},  # target_id 누락
        {"title": "   ", "body": "b", "severity": "info", "target_type": "all"},  # 빈 제목
        {"title": "t", "body": "   ", "severity": "info", "target_type": "all"},  # 빈 본문
    ],
)
async def test_admin_create_rejects_invalid_payload(admin_client, payload):
    """검증은 DB 접근 이전에 수행되므로 DB 미설정 상태에서도 400으로 실패해야 한다."""
    resp = await admin_client.post("/api/v1/admin/announcements", json=payload)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_create_returns_503_when_db_unavailable(admin_client, monkeypatch):
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await admin_client.post(
        "/api/v1/admin/announcements",
        json={"title": "정기 점검", "body": "내용", "severity": "info", "target_type": "all"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_list_returns_503_when_db_unavailable(admin_client, monkeypatch):
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await admin_client.get("/api/v1/admin/announcements")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_update_returns_503_when_db_unavailable(admin_client, monkeypatch):
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await admin_client.patch("/api/v1/admin/announcements/1", json={"title": "새 제목"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_delete_returns_503_when_db_unavailable(admin_client, monkeypatch):
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await admin_client.delete("/api/v1/admin/announcements/1")
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_user_list_returns_empty_when_db_unavailable(client, monkeypatch):
    """DB 미설정 시 사용자 목록은 에러가 아니라 빈 배열로 graceful degrade."""
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await client.get("/api/v1/announcements")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_user_unread_count_returns_zero_when_db_unavailable(client, monkeypatch):
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await client.get("/api/v1/announcements/unread-count")
    assert resp.status_code == 200
    assert resp.json() == {"unread_count": 0}


@pytest.mark.asyncio
async def test_user_mark_read_returns_404_when_db_unavailable(client, monkeypatch):
    """DB가 없으면 존재 여부를 검증할 수 없으므로 fail-closed로 404."""
    monkeypatch.setattr(announcements_service, "is_db_available", lambda: False)
    resp = await client.post("/api/v1/announcements/1/read")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_cannot_reach_admin_announcements_endpoint(client):
    """일반 유저는 관리자 공지 CRUD 엔드포인트에 접근할 수 없다."""
    resp = await client.get("/api/v1/admin/announcements")
    assert resp.status_code == 403


def test_serialize_user_payload_contract():
    """알림함 상세 보기가 의존하는 사용자 페이로드 계약을 고정한다.

    발송자(created_by_username)와 게시/만료 시각(starts_at/ends_at)은 노출하되,
    타겟 정보(target_type/target_id)는 다른 수신자 추론에 쓰일 수 있어 제외하고,
    created_by_user_id(Keystone 내부 UUID)도 일반 사용자에게 노출하지 않는다.
    """
    from datetime import UTC, datetime

    from app.models.announcement import Announcement
    from app.services.announcements import _serialize_user

    created = datetime(2026, 7, 13, 6, 0, 0, tzinfo=UTC)
    ends = datetime(2026, 7, 20, 6, 0, 0, tzinfo=UTC)
    row = Announcement(
        id=1,
        created_at=created,
        updated_at=created,
        created_by_user_id="admin-1",
        created_by_username="admin",
        title="정기 점검",
        body="본문",
        severity="info",
        target_type="all",
        target_id=None,
        starts_at=None,
        ends_at=ends,
        is_active=True,
    )

    payload = _serialize_user(row, is_read=False)

    assert payload == {
        "id": 1,
        "created_at": created.isoformat(),
        "created_by_username": "admin",
        "title": "정기 점검",
        "body": "본문",
        "severity": "info",
        "starts_at": None,
        "ends_at": ends.isoformat(),
        "is_read": False,
    }
