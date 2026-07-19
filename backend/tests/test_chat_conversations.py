"""빌트인 AI 채팅 대화/메시지 라우터 테스트.

DB 없이 conversation_store 를 monkeypatch 하여:
- 생성 시 token_info 의 project_id/user_id 가 소유자로 전달되는지(IDOR 경계)
- 타 소유자 접근 시 403(ConversationForbidden), 미존재 시 404(ConversationNotFound)
- 저장소 장애 시 503
"""

from app.services.chat import conversation_store as cs
from app.services.chat import provider_store

_URL = "/api/v1/chat/conversations"


def _public_conv(**over) -> dict:
    base = {
        "id": "conv-1",
        "project_id": "test-project-123",
        "user_id": "test-user-123",
        "title": None,
        "model_name": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(over)
    return base


class TestCreateAndList:
    async def test_create_uses_token_owner(self, client, monkeypatch):
        captured = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return _public_conv(title=kwargs.get("title"))

        monkeypatch.setattr(cs, "create_conversation", fake_create)
        resp = await client.post(_URL, json={"title": "테스트 대화"})
        assert resp.status_code == 201
        # 소유자는 반드시 token_info 에서 주입 — 클라이언트 입력이 아님.
        assert captured["project_id"] == "test-project-123"
        assert captured["user_id"] == "test-user-123"

    async def test_list_scoped_to_owner(self, client, monkeypatch):
        captured = {}

        async def fake_list(**kwargs):
            captured.update(kwargs)
            return [_public_conv()]

        monkeypatch.setattr(cs, "list_conversations", fake_list)
        resp = await client.get(_URL)
        assert resp.status_code == 200
        # 프로젝트 무관 — user_id 단독 소유. project_id 는 소유권에서 제외됨.
        assert captured["user_id"] == "test-user-123"
        assert "project_id" not in captured


class TestOwnership:
    async def test_get_forbidden_403(self, client, monkeypatch):
        async def fake_get(conv_id, **kwargs):
            raise cs.ConversationForbidden("접근 불가")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        resp = await client.get(f"{_URL}/other-project-conv")
        assert resp.status_code == 403

    async def test_get_not_found_404(self, client, monkeypatch):
        async def fake_get(conv_id, **kwargs):
            raise cs.ConversationNotFound("없음")

        monkeypatch.setattr(cs, "get_conversation", fake_get)
        resp = await client.get(f"{_URL}/nope")
        assert resp.status_code == 404

    async def test_delete_forbidden_403(self, client, monkeypatch):
        async def fake_delete(conv_id, **kwargs):
            raise cs.ConversationForbidden("접근 불가")

        monkeypatch.setattr(cs, "delete_conversation", fake_delete)
        resp = await client.delete(f"{_URL}/other-project-conv")
        assert resp.status_code == 403

    async def test_messages_forbidden_403(self, client, monkeypatch):
        async def fake_msgs(conv_id, **kwargs):
            raise cs.ConversationForbidden("접근 불가")

        monkeypatch.setattr(cs, "list_messages", fake_msgs)
        resp = await client.get(f"{_URL}/other-project-conv/messages")
        assert resp.status_code == 403


class TestStorageUnavailable:
    async def test_list_503(self, client, monkeypatch):
        async def fake_list(**kwargs):
            raise cs.ChatStorageUnavailable("DB down")

        monkeypatch.setattr(cs, "list_conversations", fake_list)
        resp = await client.get(_URL)
        assert resp.status_code == 503


class TestAvailableModels:
    async def test_returns_active_models_without_keys(self, client, monkeypatch):
        async def fake_models(*, active_only=False):
            assert active_only is True
            return [
                {
                    "id": 1,
                    "provider_id": 1,
                    "model_name": "gpt-4o",
                    "display_name": "GPT-4o",
                    "is_active": True,
                    "input_price": 0.0000025,
                    "output_price": 0.00001,
                    "created_at": None,
                    "updated_at": None,
                },
            ]

        monkeypatch.setattr(provider_store, "list_models", fake_models)
        resp = await client.get("/api/v1/chat/models")
        assert resp.status_code == 200
        body = resp.json()
        assert body == [{"model_name": "gpt-4o", "display_name": "GPT-4o"}]
        # 가격/내부 필드 미노출
        assert "input_price" not in body[0]
        assert "provider_id" not in body[0]

    async def test_graceful_empty_on_storage_unavailable(self, client, monkeypatch):
        async def fake_models(*, active_only=False):
            raise provider_store.ChatStorageUnavailable("DB down")

        monkeypatch.setattr(provider_store, "list_models", fake_models)
        resp = await client.get("/api/v1/chat/models")
        assert resp.status_code == 200
        assert resp.json() == []
