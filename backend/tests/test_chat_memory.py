"""빌트인 AI 채팅 사용자 메모리 라우터 테스트 — user 소유 주입·403/404 매핑."""

import hashlib

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


def test_memory_content_fingerprint_is_keyed(monkeypatch):
    monkeypatch.setattr(ms, "derive_encryption_subkey", lambda _domain: b"k" * 32)

    assert ms.memory_content_fingerprint("yes") != hashlib.sha256(b"yes").hexdigest()
    assert ms.memory_content_fingerprint("yes") == ms.memory_content_fingerprint("yes")
    assert ms.memory_content_fingerprint("yes") != ms.memory_content_fingerprint("no")


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

    async def test_create_project_scope_uses_token_project(self, client, monkeypatch):
        captured = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return _public(content=kwargs["content"], scope=kwargs["scope"], project_id=kwargs["project_id"])

        monkeypatch.setattr(ms, "create_memory", fake_create)
        resp = await client.post(_URL, json={"content": "프로젝트 메모리", "scope": "project"})

        assert resp.status_code == 201
        assert captured["scope"] == "project"
        assert captured["project_id"] == "test-project-123"
        assert captured["workspace_id"] is None

    async def test_account_scope_rejects_workspace_namespace(self, client):
        resp = await client.post(_URL, json={"content": "잘못된 범위", "scope": "account", "workspace_id": 7})

        assert resp.status_code == 400

    async def test_semantic_search_rehydrates_only_requested_namespace(self, client, monkeypatch):
        from types import SimpleNamespace

        from app.api.chat import memory

        captured = {}

        async def fake_resolve_model(_model_name):
            return {"model_name": "embedding"}

        async def fake_candidates(**kwargs):
            captured["candidate"] = kwargs
            return [9, 4]

        async def fake_hydrate(**kwargs):
            captured["hydrate"] = kwargs
            return [_public(id=9, scope="project", project_id="test-project-123")]

        monkeypatch.setattr(
            memory,
            "get_settings",
            lambda: SimpleNamespace(
                chat_memory_embedding_model="embedding",
                chat_memory_embedding_dimensions=3,
                chat_memory_candidate_limit=20,
            ),
        )
        monkeypatch.setattr(memory, "semantic_memory_available", lambda: True)
        monkeypatch.setattr(memory.ps, "resolve_model", fake_resolve_model)
        monkeypatch.setattr(memory.mr, "candidate_ids", fake_candidates)
        monkeypatch.setattr(memory.ms, "hydrate_candidate_ids", fake_hydrate)

        resp = await client.post(f"{_URL}/search", json={"query": "선호", "scope": "project"})

        assert resp.status_code == 200
        assert captured["candidate"]["project_id"] == "test-project-123"
        assert captured["candidate"]["workspace_id"] is None
        assert captured["hydrate"]["ids"] == [9, 4]
        assert captured["hydrate"]["scope"] == "project"

    async def test_semantic_search_fails_closed_when_index_unavailable(self, client, monkeypatch):
        from app.api.chat import memory

        monkeypatch.setattr(memory, "semantic_memory_available", lambda: False)

        response = await client.post(f"{_URL}/search", json={"query": "선호", "scope": "account"})

        assert response.status_code == 503

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
        assert captured["project_id"] == "test-project-123"

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
        assert captured["project_id"] == "test-project-123"
