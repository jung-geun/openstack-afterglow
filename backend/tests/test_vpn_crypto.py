"""WireGuard X25519 키쌍 생성 + AES-GCM 클라이언트 키 암복호화 도메인 분리 테스트."""

import base64
import re
from types import SimpleNamespace

import pytest

from app.services import vpn_keys

_VALID_KEY_HEX = "a" * 64  # 32바이트 (64 hex characters)
_OTHER_KEY_HEX = "b" * 64

_WG_KEY_RE = re.compile(r"^[A-Za-z0-9+/]{42,43}=\Z")


# ---------------------------------------------------------------------------
# X25519 키쌍 생성 (vpn_keys.py)
# ---------------------------------------------------------------------------


class TestGenerateKeypair:
    def test_returns_two_distinct_base64_44_char_keys(self):
        priv, pub = vpn_keys.generate_keypair()
        assert isinstance(priv, str)
        assert isinstance(pub, str)
        assert priv != pub

    def test_keys_match_wireguard_base64_format(self):
        """WireGuard 표준 base64 44자 형식(32바이트 + 패딩)과 일치해야 한다."""
        priv, pub = vpn_keys.generate_keypair()
        assert len(priv) == 44
        assert len(pub) == 44
        assert priv.endswith("=")
        assert pub.endswith("=")
        assert _WG_KEY_RE.match(priv)
        assert _WG_KEY_RE.match(pub)

    def test_keys_decode_to_32_raw_bytes(self):
        priv, pub = vpn_keys.generate_keypair()
        assert len(base64.b64decode(priv)) == 32
        assert len(base64.b64decode(pub)) == 32

    def test_each_call_generates_unique_keypair(self):
        pairs = [vpn_keys.generate_keypair() for _ in range(5)]
        privs = {p[0] for p in pairs}
        pubs = {p[1] for p in pairs}
        assert len(privs) == 5
        assert len(pubs) == 5

    def test_public_key_derived_from_private_key(self):
        """생성된 private key로부터 public key를 재계산하면 동일해야 한다(클램핑 호환성)."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

        priv_b64, pub_b64 = vpn_keys.generate_keypair()
        priv_bytes = base64.b64decode(priv_b64)
        priv_obj = X25519PrivateKey.from_private_bytes(priv_bytes)
        recomputed_pub = priv_obj.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        assert base64.b64encode(recomputed_pub).decode() == pub_b64


class TestGeneratePresharedKey:
    def test_returns_base64_44_char_key(self):
        psk = vpn_keys.generate_preshared_key()
        assert len(psk) == 44
        assert psk.endswith("=")
        assert _WG_KEY_RE.match(psk)

    def test_each_call_is_unique(self):
        keys = {vpn_keys.generate_preshared_key() for _ in range(5)}
        assert len(keys) == 5


# ---------------------------------------------------------------------------
# AES-256-GCM 암복호화 왕복 + 도메인 분리 (k3s_crypto.py: encrypt/decrypt_wg_client_key)
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_VALID_KEY_HEX),
    )
    yield


@pytest.fixture
def other_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_OTHER_KEY_HEX),
    )
    yield


class TestWgClientKeyRoundtrip:
    def test_encrypt_decrypt_roundtrip(self, valid_key):
        from app.services.k3s_crypto import decrypt_wg_client_key, encrypt_wg_client_key

        plaintext_priv_key, _ = vpn_keys.generate_keypair()
        ciphertext = encrypt_wg_client_key(plaintext_priv_key)
        assert ciphertext != plaintext_priv_key
        assert decrypt_wg_client_key(ciphertext) == plaintext_priv_key

    def test_ciphertext_is_not_plaintext_substring(self, valid_key):
        """평문이 암호문에 그대로 노출되지 않아야 한다."""
        from app.services.k3s_crypto import encrypt_wg_client_key

        plaintext = "a-very-recognizable-private-key-value=="
        ciphertext = encrypt_wg_client_key(plaintext)
        assert plaintext not in ciphertext

    def test_two_encryptions_of_same_plaintext_differ(self, valid_key):
        """AES-GCM은 매번 랜덤 nonce를 사용하므로 같은 평문도 암호문이 달라야 한다."""
        from app.services.k3s_crypto import encrypt_wg_client_key

        plaintext = "same-plaintext-key-value"
        ct1 = encrypt_wg_client_key(plaintext)
        ct2 = encrypt_wg_client_key(plaintext)
        assert ct1 != ct2


class TestWgClientKeyDomainSeparation:
    """도메인 분리 검증: wg_client_key 도메인으로 암호화된 값은 다른 도메인(k3s kubeconfig 등)
    함수로 복호화할 수 없어야 한다 — HKDF 서브키가 도메인별로 분리되기 때문."""

    def test_wg_client_key_ciphertext_fails_kubeconfig_decrypt(self, valid_key):
        from app.services.k3s_crypto import decrypt_kubeconfig, encrypt_wg_client_key

        ciphertext = encrypt_wg_client_key("wg-private-key-value")
        with pytest.raises(Exception):
            decrypt_kubeconfig(ciphertext)

    def test_kubeconfig_ciphertext_fails_wg_client_key_decrypt(self, valid_key):
        from app.services.k3s_crypto import decrypt_wg_client_key, encrypt_kubeconfig

        ciphertext = encrypt_kubeconfig("apiVersion: v1\nkind: Config\n")
        with pytest.raises(Exception):
            decrypt_wg_client_key(ciphertext)

    def test_wg_client_key_ciphertext_fails_node_token_decrypt(self, valid_key):
        from app.services.k3s_crypto import decrypt_node_token, encrypt_wg_client_key

        ciphertext = encrypt_wg_client_key("wg-private-key-value")
        with pytest.raises(Exception):
            decrypt_node_token(ciphertext)

    def test_decrypt_fails_with_different_master_key(self, valid_key, monkeypatch):
        """같은 도메인이라도 마스터 키가 다르면 복호화가 실패해야 한다."""
        from app.services.k3s_crypto import decrypt_wg_client_key, encrypt_wg_client_key

        ciphertext = encrypt_wg_client_key("wg-private-key-value")

        monkeypatch.setattr(
            "app.services.k3s_crypto.get_settings",
            lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=_OTHER_KEY_HEX),
        )
        with pytest.raises(Exception):
            decrypt_wg_client_key(ciphertext)
