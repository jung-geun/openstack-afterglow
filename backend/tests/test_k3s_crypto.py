"""AES-256-GCM 암복호화 단위 테스트 (k3s_crypto.py).

k3s_crypto.py는 kubeconfig/node-token/notion-config를 AES-256-GCM으로
암호화한다. v2: prefix = AAD 바인딩, prefix 없음 = 레거시(AAD 없음).
"""

import base64
import os
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 64자 유효한 hex 키 (모두 'a' → 0xaa*32)
_VALID_KEY_HEX = "a" * 64
_VALID_KEY_BYTES = bytes.fromhex(_VALID_KEY_HEX)
# notion 전용 키 (k3s 키와 다름)
_NOTION_KEY_HEX = "b" * 64
_NOTION_KEY_BYTES = bytes.fromhex(_NOTION_KEY_HEX)
# 완전히 다른 키 (wrong key 테스트용)
_OTHER_KEY_BYTES = bytes.fromhex("c" * 64)


@pytest.fixture
def valid_keys(monkeypatch):
    """k3s + notion 키를 유효한 테스트 키로 교체."""
    monkeypatch.setattr("app.services.k3s_crypto._get_key", lambda: _VALID_KEY_BYTES)
    monkeypatch.setattr("app.services.k3s_crypto._get_notion_key", lambda: _NOTION_KEY_BYTES)


# ---------------------------------------------------------------------------
# 기본 암복호화 (v2 경로)
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_encrypt_kubeconfig_returns_v2_prefix(valid_keys):
    from app.services.k3s_crypto import encrypt_kubeconfig

    ct = encrypt_kubeconfig("apiVersion: v1")
    assert ct.startswith("v2:")


@pytest.mark.crypto
def test_decrypt_kubeconfig_roundtrip_v2(valid_keys):
    from app.services.k3s_crypto import decrypt_kubeconfig, encrypt_kubeconfig

    plaintext = "apiVersion: v1\nkind: Config\n"
    assert decrypt_kubeconfig(encrypt_kubeconfig(plaintext)) == plaintext


@pytest.mark.crypto
def test_decrypt_node_token_roundtrip_v2(valid_keys):
    from app.services.k3s_crypto import decrypt_node_token, encrypt_node_token

    token = "K1234567890abcdef::secret"
    assert decrypt_node_token(encrypt_node_token(token)) == token


@pytest.mark.crypto
def test_decrypt_notion_config_roundtrip(valid_keys):
    from app.services.k3s_crypto import decrypt_notion_config, encrypt_notion_config

    api_key = "secret-notion-api-key"
    assert decrypt_notion_config(encrypt_notion_config(api_key)) == api_key


# ---------------------------------------------------------------------------
# 레거시 v1 경로 (AAD 없이 만든 ciphertext)
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_decrypt_kubeconfig_legacy_v1(valid_keys):
    """prefix 없는 레거시 ciphertext(AAD=None)도 복호화 가능."""
    from app.services.k3s_crypto import decrypt_kubeconfig

    aesgcm = AESGCM(_VALID_KEY_BYTES)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, b"legacy plaintext", None)
    legacy_b64 = base64.b64encode(nonce + ct).decode()
    assert decrypt_kubeconfig(legacy_b64) == "legacy plaintext"


@pytest.mark.crypto
def test_legacy_decrypt_does_not_attempt_aad(valid_keys):
    """prefix 없는 레거시 node_token ciphertext를 AAD 없이 복호화 성공."""
    from app.services.k3s_crypto import decrypt_node_token

    aesgcm = AESGCM(_VALID_KEY_BYTES)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, b"legacy node token", None)
    legacy_b64 = base64.b64encode(nonce + ct).decode()
    assert decrypt_node_token(legacy_b64) == "legacy node token"


# ---------------------------------------------------------------------------
# AAD 바인딩 — cross-AAD 거부
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_decrypt_kubeconfig_aad_mismatch_raises(valid_keys):
    """node_token AAD로 만든 v2 ciphertext를 kubeconfig로 복호화 → InvalidTag."""
    from app.services.k3s_crypto import decrypt_kubeconfig, encrypt_node_token

    ct = encrypt_node_token("K1234::secret")
    with pytest.raises(InvalidTag):
        decrypt_kubeconfig(ct)


@pytest.mark.crypto
def test_node_token_aad_isolation(valid_keys):
    """kubeconfig AAD로 만든 v2 ciphertext를 node_token으로 복호화 → InvalidTag."""
    from app.services.k3s_crypto import decrypt_node_token, encrypt_kubeconfig

    ct = encrypt_kubeconfig("apiVersion: v1")
    with pytest.raises(InvalidTag):
        decrypt_node_token(ct)


@pytest.mark.crypto
def test_decrypt_kubeconfig_wrong_key_raises(valid_keys):
    """다른 키로 만든 v2 ciphertext → InvalidTag."""
    from app.services.k3s_crypto import _aes_encrypt, decrypt_kubeconfig

    ct = _aes_encrypt(_OTHER_KEY_BYTES, "plain", aad=b"kubeconfig")
    with pytest.raises(InvalidTag):
        decrypt_kubeconfig(ct)


# ---------------------------------------------------------------------------
# _get_key 입력 검증
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_get_key_short_hex_raises(monkeypatch):
    from app.services.k3s_crypto import _get_key

    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key="a" * 32),
    )
    with pytest.raises(ValueError, match="64 hex characters"):
        _get_key()


@pytest.mark.crypto
def test_get_key_non_hex_raises(monkeypatch):
    from app.services.k3s_crypto import _get_key

    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key="g" * 64),
    )
    with pytest.raises(ValueError):
        _get_key()


@pytest.mark.crypto
def test_get_key_empty_raises(monkeypatch):
    from app.services.k3s_crypto import _get_key

    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(k3s_kubeconfig_encryption_key=""),
    )
    with pytest.raises(ValueError, match="64 hex characters"):
        _get_key()


# ---------------------------------------------------------------------------
# Notion 키 — 분리 / 폴백
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_notion_config_uses_separate_key(valid_keys):
    """notion 키가 k3s 키와 다를 때 각자 독립적으로 암복호화."""
    from app.services.k3s_crypto import decrypt_notion_config, encrypt_notion_config

    ct = encrypt_notion_config("notion_api_key_123")
    assert decrypt_notion_config(ct) == "notion_api_key_123"


@pytest.mark.crypto
def test_notion_config_falls_back_to_k3s_key(monkeypatch):
    """notion_config_encryption_key 미설정 시 k3s 키 재사용 — 의도된 동작."""
    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(
            notion_config_encryption_key="",
            k3s_kubeconfig_encryption_key=_VALID_KEY_HEX,
        ),
    )
    from app.services.k3s_crypto import _get_notion_key

    assert _get_notion_key() == _VALID_KEY_BYTES


@pytest.mark.crypto
def test_notion_config_cross_key_rejection(valid_keys):
    """k3s ciphertext를 notion 키로 복호화 불가 (키가 다름)."""
    from app.services.k3s_crypto import decrypt_notion_config, encrypt_kubeconfig

    ct = encrypt_kubeconfig("some config")
    with pytest.raises(InvalidTag):
        decrypt_notion_config(ct)


# ---------------------------------------------------------------------------
# ciphertext 구조
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_v2_prefix_is_3_chars_exact(valid_keys):
    from app.services.k3s_crypto import _V2_PREFIX, encrypt_kubeconfig

    assert _V2_PREFIX == "v2:"
    ct = encrypt_kubeconfig("test")
    # prefix 뒤는 base64 시작 (알파벳 또는 숫자)
    assert ct[3:4].isalnum() or ct[3:4] in ("+", "/")


@pytest.mark.crypto
def test_nonce_is_12_bytes(valid_keys):
    """암호화 결과의 base64 raw 첫 12바이트가 nonce."""
    from app.services.k3s_crypto import _V2_PREFIX, encrypt_kubeconfig

    ct = encrypt_kubeconfig("nonce check")
    raw = base64.b64decode(ct[len(_V2_PREFIX) :])
    # nonce(12) + ciphertext + GCM tag(16)
    assert len(raw) > 12
    nonce = raw[:12]
    assert len(nonce) == 12


@pytest.mark.crypto
def test_decrypt_invalid_base64_raises(valid_keys):
    from app.services.k3s_crypto import decrypt_kubeconfig

    with pytest.raises(Exception):
        decrypt_kubeconfig("v2:!!!notbase64!!!")


@pytest.mark.crypto
def test_decrypt_truncated_ciphertext_raises(valid_keys):
    """nonce보다 짧은 raw bytes → 복호화 시도 시 에러."""
    from app.services.k3s_crypto import decrypt_kubeconfig

    short = base64.b64encode(b"short").decode()
    with pytest.raises(Exception):
        decrypt_kubeconfig(f"v2:{short}")


# ---------------------------------------------------------------------------
# nonce 무작위성
# ---------------------------------------------------------------------------


@pytest.mark.crypto
def test_concurrent_encrypt_unique_nonces(valid_keys):
    """같은 plaintext 100회 암호화 → 모두 다른 ciphertext (nonce 재사용 없음)."""
    from app.services.k3s_crypto import encrypt_kubeconfig

    results = {encrypt_kubeconfig("same payload") for _ in range(100)}
    assert len(results) == 100
