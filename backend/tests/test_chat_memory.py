"""빌트인 AI 채팅 사용자 메모리 라우터 테스트 — user 소유 주입·403/404 매핑."""

from app.services.chat import memory_store as ms

_URL = "/api/v1/chat/memories"


def _public(**over) -> dict:
    base = {
        "id": 1,
        "user_id": "test-user-123",
        "content": "사용자는 Python 을 선호",
        "is_active": True,
        "created_at": None,
        "updated_at": None,
    }
    base.update(over)
    return base


class TestCrud:
    async def test_create_injects_user(self, client, monkeypatch):
        captured = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return _public(content=kwargs["content"])

        monkeypatch.setattr(ms, "create_memory", fake_create)
        resp = await client.post(_URL, json={"content": "다크모드 선호"})
        assert resp.status_code == 201
        assert captured["user_id"] == "test-user-123"
        assert captured["content"] == "다크모드 선호"

    async def test_create_requires_content(self, client):
        resp = await client.post(_URL, json={"content": ""})
        assert resp.status_code == 422  # min_length=1

    async def test_list(self, client, monkeypatch):
        captured = {}

        async def fake_list(**kwargs):
            captured.update(kwargs)
            return [_public()]

        monkeypatch.setattr(ms, "list_memories", fake_list)
        resp = await client.get(_URL)
        assert resp.status_code == 200
        assert captured["user_id"] == "test-user-123"

    async def test_list_graceful_empty_on_storage_unavailable(self, client, monkeypatch):
        """저장소 미가용/데이터 없음은 503 이 아니라 빈 목록(200)으로 degrade."""

        async def fake_list(**kwargs):
            raise ms.ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")

        monkeypatch.setattr(ms, "list_memories", fake_list)
        resp = await client.get(_URL)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_update_forbidden_403(self, client, monkeypatch):
        async def fake_update(mid, **kwargs):
            raise ms.MemoryForbidden("타인")

        monkeypatch.setattr(ms, "update_memory", fake_update)
        resp = await client.patch(f"{_URL}/9", json={"is_active": False})
        assert resp.status_code == 403

    async def test_delete(self, client, monkeypatch):
        captured = {}

        async def fake_delete(mid, **kwargs):
            captured["mid"] = mid
            captured.update(kwargs)

        monkeypatch.setattr(ms, "delete_memory", fake_delete)
        resp = await client.delete(f"{_URL}/9")
        assert resp.status_code == 204
        assert captured["mid"] == 9 and captured["user_id"] == "test-user-123"
