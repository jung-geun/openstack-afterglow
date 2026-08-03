"""빌트인 AI 채팅 LLM 프로바이더 API 키 AES-256-GCM 암복호화 + 도메인 분리 테스트.

k3s_crypto.py 의 encrypt/decrypt_llm_provider_key 는 기존 k3s 마스터키를 재사용하되
도메인(llm_provider_key)을 분리하므로, 다른 도메인 ciphertext 와 교차 복호화되지 않아야 한다.
외부 인프라 불요 — crypto 단위 테스트.
"""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.crypto

_VALID_KEY_HEX = "a" * 64  # 32바이트 (64 hex characters)
_OTHER_KEY_HEX = "b" * 64


@pytest.fixture
def valid_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_VALID_KEY_HEX),
    )


class TestLlmProviderKeyCrypto:
    def test_roundtrip(self, valid_key):
        from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_llm_provider_key

        plaintext = "sk-provider-secret-abcdef0123456789"
        ciphertext = encrypt_llm_provider_key(plaintext)
        assert ciphertext != plaintext
        assert decrypt_llm_provider_key(ciphertext) == plaintext

    def test_ciphertext_uses_v3_prefix(self, valid_key):
        from app.services.k3s_crypto import encrypt_llm_provider_key

        ciphertext = encrypt_llm_provider_key("sk-abc")
        assert ciphertext.startswith("v3:")

    def test_nonce_randomized(self, valid_key):
        from app.services.k3s_crypto import encrypt_llm_provider_key

        # 동일 평문이라도 nonce 랜덤화로 매번 다른 ciphertext.
        ct1 = encrypt_llm_provider_key("sk-abc")
        ct2 = encrypt_llm_provider_key("sk-abc")
        assert ct1 != ct2

    def test_domain_separation_kubeconfig_cannot_decrypt(self, valid_key):
        """llm 도메인 ciphertext 를 kubeconfig 도메인 키로 복호화하면 실패해야 한다."""
        from app.services.k3s_crypto import decrypt_kubeconfig, encrypt_llm_provider_key

        ciphertext = encrypt_llm_provider_key("sk-provider-secret")
        with pytest.raises(Exception):
            decrypt_kubeconfig(ciphertext)

    def test_domain_separation_reverse(self, valid_key):
        """kubeconfig 도메인 ciphertext 를 llm 도메인 키로 복호화하면 실패해야 한다."""
        from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_kubeconfig

        ciphertext = encrypt_kubeconfig("apiVersion: v1")
        with pytest.raises(Exception):
            decrypt_llm_provider_key(ciphertext)

    def test_decrypt_fails_with_different_master_key(self, valid_key, monkeypatch):
        from app.services.k3s_crypto import decrypt_llm_provider_key, encrypt_llm_provider_key

        ciphertext = encrypt_llm_provider_key("sk-provider-secret")
        monkeypatch.setattr(
            "app.services.k3s_crypto.get_settings",
            lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_OTHER_KEY_HEX),
        )
        with pytest.raises(Exception):
            decrypt_llm_provider_key(ciphertext)
