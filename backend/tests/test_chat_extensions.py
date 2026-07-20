"""빌트인 AI 채팅 확장(MCP/커스텀툴) 라우터 테스트.

DB 없이 extensions_store 를 monkeypatch 하여:
- 관리자 라우터 require_admin 게이트 + scope='global' 생성
- 사용자 라우터: 생성 시 scope='user' + 소유자(token) 주입, 타 소유자 접근 403
- 검증 실패 400, 저장소 장애 503
"""

from app.services.chat import extensions_store as es

_ADMIN_MCP = "/api/v1/chat/admin/mcp-servers"
_ADMIN_TOOL = "/api/v1/chat/admin/custom-tools"
_USER_MCP = "/api/v1/chat/mcp-servers"
_USER_TOOL = "/api/v1/chat/custom-tools"


class TestAdminGate:
    async def test_admin_mcp_forbidden_for_non_admin(self, non_admin_client):
        assert (await non_admin_client.get(_ADMIN_MCP)).status_code == 403

    async def test_admin_tool_create_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.post(_ADMIN_TOOL, json={"name": "x", "url": "https://e.com"})
        assert resp.status_code == 403


class TestAdminGlobal:
    async def test_admin_create_mcp_is_global(self, admin_client, monkeypatch):
        captured = {}

        async def fake_create(kind, fields, **kwargs):
            captured["kind"] = kind
            captured.update(kwargs)
            return {"id": 1, "scope": kwargs.get("scope"), "name": fields.get("name")}

        monkeypatch.setattr(es, "create", fake_create)
        resp = await admin_client.post(
            _ADMIN_MCP, json={"name": "ctx7", "transport": "http", "url": "https://mcp.example"}
        )
        assert resp.status_code == 201
        assert captured["kind"] == "mcp"
        assert captured["scope"] == "global"


class TestUserScope:
    async def test_user_create_tool_scoped_to_owner(self, client, monkeypatch):
        captured = {}

        async def fake_create(kind, fields, **kwargs):
            captured["kind"] = kind
            captured["fields"] = fields
            captured.update(kwargs)
            return {"id": 5, "scope": "user", "name": fields.get("name")}

        monkeypatch.setattr(es, "create", fake_create)
        resp = await client.post(
            _USER_TOOL,
            json={"name": "weather", "description": "날씨", "method": "GET", "url": "https://api.example/w"},
        )
        assert resp.status_code == 201
        assert captured["kind"] == "tool"
        assert captured["scope"] == "user"
        assert captured["owner_user_id"] == "test-user-123"
        assert captured["owner_project_id"] == "test-project-123"

    async def test_user_update_foreign_forbidden(self, client, monkeypatch):
        async def fake_update(kind, item_id, patch, **kwargs):
            raise es.ExtensionForbidden("소유자가 아닙니다")

        monkeypatch.setattr(es, "update", fake_update)
        resp = await client.patch(f"{_USER_MCP}/999", json={"is_active": False})
        assert resp.status_code == 403

    async def test_user_delete_passes_owner_context(self, client, monkeypatch):
        captured = {}

        async def fake_delete(kind, item_id, **kwargs):
            captured.update(kwargs)

        monkeypatch.setattr(es, "delete", fake_delete)
        resp = await client.delete(f"{_USER_TOOL}/3")
        assert resp.status_code == 204
        assert captured["requester_user_id"] == "test-user-123"
        assert captured["requester_project_id"] == "test-project-123"

    async def test_user_list_mcp_ok(self, client, monkeypatch):
        async def fake_list(kind, **kwargs):
            return [{"id": 1, "scope": "global", "name": "shared"}]

        monkeypatch.setattr(es, "list_for_user", fake_list)
        resp = await client.get(_USER_MCP)
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "shared"

    async def test_user_list_graceful_empty_on_storage_unavailable(self, client, monkeypatch):
        """사용자 MCP/Skill 목록은 저장소 미가용 시 빈 목록(200)으로 degrade(관리자 목록은 503 유지)."""

        async def fake_list(kind, **kwargs):
            raise es.ChatStorageUnavailable("chat DB 를 사용할 수 없습니다")

        monkeypatch.setattr(es, "list_for_user", fake_list)
        assert (await client.get(_USER_MCP)).json() == []
        assert (await client.get(_USER_MCP)).status_code == 200
        assert (await client.get(_USER_TOOL)).json() == []
        assert (await client.get(_USER_TOOL)).status_code == 200


class TestErrors:
    async def test_validation_400(self, client, monkeypatch):
        async def fake_create(kind, fields, **kwargs):
            raise es.ExtensionValidationError("url 필수")

        monkeypatch.setattr(es, "create", fake_create)
        resp = await client.post(_USER_TOOL, json={"name": "bad"})
        assert resp.status_code == 400

    async def test_storage_unavailable_503(self, admin_client, monkeypatch):
        async def fake_list(kind):
            raise es.ChatStorageUnavailable("DB down")

        monkeypatch.setattr(es, "list_global", fake_list)
        resp = await admin_client.get(_ADMIN_TOOL)
        assert resp.status_code == 503
