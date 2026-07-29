"""원격 MCP 서버 설정 하드닝 — store 단위 테스트 (DB 불요).

검증 대상(보안 핵심):
- transport 화이트리스트: HTTPS streamable HTTP만 허용, SSE·stdio 거부.
- url 스킴 검증(https:// 필수).
- 인증 헤더 암호화 저장(encrypted_headers) + 조회 시 마스킹(_public_mcp).
- 실행 경로(_reveal_mcp)는 복호화된 실제 헤더 노출.
- 레거시 plaintext headers 하위호환.
- 마스킹 sentinel 재저장 시 기존 헤더 보존(값 유실 방지).

crypto 마스터키를 patch 해 DB/외부 인프라 없이 순수 로직만 검증한다.
"""

from types import SimpleNamespace

import pytest

from app.models.chat_db import ChatMcpServer
from app.services.chat import extensions_store as es

_VALID_KEY_HEX = "a" * 64


@pytest.fixture(autouse=True)
def _crypto_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_VALID_KEY_HEX),
    )


def _row(**kw) -> ChatMcpServer:
    row = ChatMcpServer()
    row.id = kw.pop("id", 1)
    row.scope = kw.pop("scope", "user")
    row.name = kw.pop("name", "srv")
    row.transport = kw.pop("transport", "http")
    row.url = kw.pop("url", "https://mcp.example/mcp")
    row.command = None
    row.headers = kw.pop("headers", None)
    row.encrypted_headers = kw.pop("encrypted_headers", None)
    row.auth_requirements = kw.pop("auth_requirements", None)
    row.is_active = kw.pop("is_active", True)
    row.created_at = None
    return row


class TestTransportWhitelist:
    def test_only_streamable_http_allowed(self):
        row = _row()
        es._apply_fields("mcp", row, {"transport": "http"})
        assert row.transport == "http"
        for transport in ("sse", "stdio", "grpc"):
            with pytest.raises(es.ExtensionValidationError):
                es._apply_fields("mcp", row, {"transport": transport})

    def test_legacy_sse_is_rejected(self):
        row = _row()
        with pytest.raises(es.ExtensionValidationError):
            es._apply_fields("mcp", row, {"transport": "sse"})


class TestUrlValidation:
    def test_non_https_scheme_rejected(self):
        row = _row()
        for url in ("ftp://mcp.example", "http://mcp.example"):
            with pytest.raises(es.ExtensionValidationError):
                es._apply_fields("mcp", row, {"url": url})

    def test_https_accepted(self):
        row = _row()
        es._apply_fields("mcp", row, {"url": "https://mcp.example/mcp"})
        assert row.url == "https://mcp.example/mcp"

    def test_hosted_notion_is_classified_as_oauth(self):
        row = _row()
        es._apply_fields("mcp", row, {"url": "https://mcp.notion.com/mcp/"})
        assert row.auth_mode == "oauth"
        assert es._public_mcp(row)["auth_mode"] == "oauth"


class TestHeaderEncryption:
    def test_headers_encrypted_at_rest_not_plaintext(self):
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer secret-token"}})
        assert row.encrypted_headers  # 암호문 존재
        assert "secret-token" not in row.encrypted_headers  # 평문 유출 없음
        assert row.headers is None  # 레거시 컬럼 비움

    def test_public_masks_header_values(self):
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer secret-token", "X-Api-Key": "k"}})
        pub = es._public_mcp(row)
        assert set(pub["headers"].keys()) == {"Authorization", "X-Api-Key"}
        assert "secret-token" not in str(pub)  # 값 노출 없음
        assert pub["has_headers"] is True
        assert "command" not in pub  # stdio 잔재 제거

    def test_reveal_returns_real_headers(self):
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer secret-token"}})
        revealed = es._reveal_mcp(row)
        assert revealed["headers"] == {"Authorization": "Bearer secret-token"}

    def test_legacy_plaintext_headers_still_readable(self):
        """구 행(암호화 이전)은 plaintext headers 로 폴백해 실행/조회 가능."""
        row = _row(headers={"Authorization": "Bearer legacy"}, encrypted_headers=None)
        assert es._reveal_mcp(row)["headers"] == {"Authorization": "Bearer legacy"}
        assert es._public_mcp(row)["headers"] == {"Authorization": "••••••"}

    def test_mask_sentinel_preserves_existing_headers(self):
        """편집 폼이 마스킹 값(••••••)을 그대로 재전송해도 기존 시크릿을 덮어쓰지 않는다."""
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer real"}})
        es._apply_fields("mcp", row, {"headers": {"Authorization": "••••••"}})
        assert es._reveal_mcp(row)["headers"] == {"Authorization": "Bearer real"}

    def test_partial_edit_keeps_untouched_headers(self):
        """일부만 편집(하나는 새 값, 하나는 마스킹 유지) 시 두 헤더 모두 올바르게 보존된다."""
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer real", "X-Api-Key": "key123"}})
        # 하나만 새 값으로 교체하고 나머지는 마스킹 sentinel 재전송.
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer NEW", "X-Api-Key": "••••••"}})
        assert es._reveal_mcp(row)["headers"] == {"Authorization": "Bearer NEW", "X-Api-Key": "key123"}

    def test_partial_edit_adds_new_header(self):
        """기존 유지 + 새 헤더 추가."""
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer real"}})
        es._apply_fields("mcp", row, {"headers": {"Authorization": "••••••", "X-Extra": "v"}})
        assert es._reveal_mcp(row)["headers"] == {"Authorization": "Bearer real", "X-Extra": "v"}

    def test_empty_dict_clears_headers(self):
        row = _row()
        es._apply_fields("mcp", row, {"headers": {"Authorization": "Bearer real"}})
        es._apply_fields("mcp", row, {"headers": {}})
        assert row.encrypted_headers is None
        assert es._reveal_mcp(row)["headers"] == {}


class TestAuthRequirements:
    """사용자별 인증 요구사항(공용 시크릿 주입 없이 요구만 선언)."""

    def test_requirements_normalized_and_public(self):
        row = _row()
        es._apply_fields(
            "mcp",
            row,
            {"auth_requirements": [{"key": "Authorization", "label": "Notion Token"}, {"key": ""}, "junk"]},
        )
        pub = es._public_mcp(row)
        assert pub["auth_requirements"] == [{"key": "Authorization", "label": "Notion Token"}]

    def test_invalid_requirements_rejected(self):
        row = _row()
        with pytest.raises(es.ExtensionValidationError):
            es._apply_fields("mcp", row, {"auth_requirements": "notalist"})

    def test_credential_status_satisfied(self):
        row = _row(auth_requirements=[{"key": "Authorization", "label": "L"}])
        assert es._credential_status(row, {})["satisfied"] is False
        assert es._credential_status(row, {"Authorization": "Bearer x"})["satisfied"] is True
        assert es._credential_status(row, {"Authorization": "Bearer x"})["filled_keys"] == ["Authorization"]

    def test_no_requirements_is_satisfied(self):
        row = _row(auth_requirements=None)
        assert es._credential_status(row, {})["satisfied"] is True
