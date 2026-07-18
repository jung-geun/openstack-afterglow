"""빌트인 AI 채팅 관리자 프로바이더/모델 CRUD 라우터 테스트.

DB 없이 provider_store 서비스 함수를 monkeypatch 하여 라우터 계약만 검증:
- require_admin 게이트(비관리자 403)
- api_key 응답 마스킹(has_api_key 만, 평문/암호문 미노출)
- 예외 → HTTP 상태 매핑(404/400/503)
"""

from app.services.chat import provider_store as ps

_PROVIDERS_URL = "/api/v1/chat/admin/providers"
_MODELS_URL = "/api/v1/chat/admin/models"


def _public_provider(**over) -> dict:
    base = {
        "id": 1,
        "name": "openai",
        "provider_type": "openai",
        "api_base": None,
        "has_api_key": True,
        "is_active": True,
        "margin_multiplier": 1.0,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(over)
    return base


class TestAdminGate:
    async def test_list_providers_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.get(_PROVIDERS_URL)
        assert resp.status_code == 403

    async def test_create_provider_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.post(_PROVIDERS_URL, json={"name": "x"})
        assert resp.status_code == 403

    async def test_create_model_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.post(_MODELS_URL, json={"provider_id": 1, "model_name": "gpt-4o"})
        assert resp.status_code == 403


class TestProviderCrud:
    async def test_create_masks_api_key(self, admin_client, monkeypatch):
        captured = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return _public_provider(name=kwargs["name"], has_api_key=bool(kwargs.get("api_key")))

        monkeypatch.setattr(ps, "create_provider", fake_create)

        resp = await admin_client.post(
            _PROVIDERS_URL,
            json={"name": "openai", "api_key": "sk-super-secret-1234567890", "margin_multiplier": 1.2},
        )
        assert resp.status_code == 201
        body = resp.json()
        # 서비스는 평문 키를 전달받았지만, 응답에는 절대 노출되지 않아야 한다.
        assert captured["api_key"] == "sk-super-secret-1234567890"
        assert "api_key" not in body
        assert "encrypted_api_key" not in body
        assert body["has_api_key"] is True

    async def test_list_ok(self, admin_client, monkeypatch):
        async def fake_list():
            return [_public_provider()]

        monkeypatch.setattr(ps, "list_providers", fake_list)
        resp = await admin_client.get(_PROVIDERS_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert "api_key" not in body[0]

    async def test_update_not_found_404(self, admin_client, monkeypatch):
        async def fake_update(provider_id, patch):
            raise ps.ProviderNotFoundError("없음")

        monkeypatch.setattr(ps, "update_provider", fake_update)
        resp = await admin_client.patch(f"{_PROVIDERS_URL}/999", json={"is_active": False})
        assert resp.status_code == 404

    async def test_create_validation_400(self, admin_client, monkeypatch):
        async def fake_create(**kwargs):
            raise ps.ProviderValidationError("중복")

        monkeypatch.setattr(ps, "create_provider", fake_create)
        resp = await admin_client.post(_PROVIDERS_URL, json={"name": "dup"})
        assert resp.status_code == 400

    async def test_storage_unavailable_503(self, admin_client, monkeypatch):
        async def fake_list():
            raise ps.ChatStorageUnavailable("DB down")

        monkeypatch.setattr(ps, "list_providers", fake_list)
        resp = await admin_client.get(_PROVIDERS_URL)
        assert resp.status_code == 503


class TestModelCrud:
    async def test_create_model_ok(self, admin_client, monkeypatch):
        async def fake_create(**kwargs):
            return {
                "id": 5,
                "provider_id": kwargs["provider_id"],
                "model_name": kwargs["model_name"],
                "display_name": kwargs.get("display_name"),
                "is_active": True,
                "input_price": None,
                "output_price": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }

        monkeypatch.setattr(ps, "create_model", fake_create)
        resp = await admin_client.post(_MODELS_URL, json={"provider_id": 1, "model_name": "gpt-4o"})
        assert resp.status_code == 201
        assert resp.json()["model_name"] == "gpt-4o"

    async def test_create_model_bad_provider_400(self, admin_client, monkeypatch):
        async def fake_create(**kwargs):
            raise ps.ProviderValidationError("프로바이더 없음")

        monkeypatch.setattr(ps, "create_model", fake_create)
        resp = await admin_client.post(_MODELS_URL, json={"provider_id": 999, "model_name": "x"})
        assert resp.status_code == 400
