"""HKDF v3 sub-key 도메인 분리 + v2/legacy fallback 검증.

핵심 보안 속성: 도메인별 sub-key 가 서로 다르므로, 한 도메인의 ciphertext 가
다른 도메인 키로 복호화되지 않는다 (마스터키 자체가 같아도 분리됨).
"""

import base64
import os

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VALID_KEY_HEX = "a" * 64
_VALID_KEY_BYTES = bytes.fromhex(_VALID_KEY_HEX)


@pytest.fixture
def valid_keys(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.k3s_crypto.get_settings",
        lambda: SimpleNamespace(
            k3s_kubeconfig_encryption_key=_VALID_KEY_HEX,
            notion_config_encryption_key=None,
        ),
    )


@pytest.mark.crypto
def test_subkey_differs_by_domain(valid_keys):
    """동일 마스터키 + 다른 도메인 → 다른 sub-key bytes."""
    from app.services.k3s_crypto import _DOMAIN_KUBECONFIG, _DOMAIN_NODE_TOKEN, _derive_subkey

    k_kubeconfig = _derive_subkey(_VALID_KEY_BYTES, _DOMAIN_KUBECONFIG)
    k_node = _derive_subkey(_VALID_KEY_BYTES, _DOMAIN_NODE_TOKEN)
    assert k_kubeconfig != k_node
    assert len(k_kubeconfig) == 32
    assert len(k_node) == 32


@pytest.mark.crypto
def test_v3_kubeconfig_decrypt_node_token_rejects(valid_keys):
    """kubeconfig sub-key 로 만든 v3 ciphertext 를 node_token sub-key 로 복호화 → InvalidTag."""
    from app.services.k3s_crypto import decrypt_node_token, encrypt_kubeconfig

    ct = encrypt_kubeconfig("apiVersion: v1")
    assert ct.startswith("v3:")
    with pytest.raises(InvalidTag):
        decrypt_node_token(ct)


@pytest.mark.crypto
def test_v3_node_token_decrypt_manager_password_rejects(valid_keys):
    """node_token sub-key 로 만든 v3 ciphertext 를 manager_password sub-key 로 복호화 → InvalidTag."""
    from app.services.k3s_crypto import decrypt_manager_password, encrypt_node_token

    ct = encrypt_node_token("K10::secret")
    with pytest.raises(InvalidTag):
        decrypt_manager_password(ct)


@pytest.mark.crypto
def test_v3_round_trip_all_domains(valid_keys):
    from app.services.k3s_crypto import (
        decrypt_kubeconfig,
        decrypt_manager_password,
        decrypt_node_token,
        decrypt_notion_config,
        encrypt_kubeconfig,
        encrypt_manager_password,
        encrypt_node_token,
        encrypt_notion_config,
    )

    for enc, dec, plain in [
        (encrypt_kubeconfig, decrypt_kubeconfig, "apiVersion: v1\n"),
        (encrypt_node_token, decrypt_node_token, "K10:host:abc"),
        (encrypt_notion_config, decrypt_notion_config, "secret_xxx"),
        (encrypt_manager_password, decrypt_manager_password, "P@ssw0rd!"),
    ]:
        ct = enc(plain)
        assert ct.startswith("v3:")
        assert dec(ct) == plain


@pytest.fixture
def reset_legacy_warned():
    """다른 테스트가 이미 warn 한 도메인이 있으면 caplog 에 안 잡히므로 reset."""
    from app.services import k3s_crypto

    k3s_crypto._LEGACY_WARNED.clear()
    yield
    k3s_crypto._LEGACY_WARNED.clear()


@pytest.mark.crypto
def test_v2_fallback_still_decrypts_with_warning(valid_keys, caplog, reset_legacy_warned):
    """기존 v2: prefix ciphertext 는 fallback 으로 복호화 + deprecation warning."""
    from app.services.k3s_crypto import _DOMAIN_KUBECONFIG, decrypt_kubeconfig

    aesgcm = AESGCM(_VALID_KEY_BYTES)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, b"legacy v2 kubeconfig", _DOMAIN_KUBECONFIG)
    v2_b64 = "v2:" + base64.b64encode(nonce + ct).decode()

    import logging

    with caplog.at_level(logging.WARNING, logger="app.services.k3s_crypto"):
        result = decrypt_kubeconfig(v2_b64)

    assert result == "legacy v2 kubeconfig"
    assert any("v2" in r.message for r in caplog.records)


@pytest.mark.crypto
def test_legacy_no_prefix_fallback_with_warning(valid_keys, caplog, reset_legacy_warned):
    """접두사 없는 legacy ciphertext (AAD 없음) 도 fallback 으로 복호화 + warning."""
    from app.services.k3s_crypto import decrypt_node_token

    aesgcm = AESGCM(_VALID_KEY_BYTES)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, b"legacy node token", None)
    legacy_b64 = base64.b64encode(nonce + ct).decode()

    import logging

    with caplog.at_level(logging.WARNING, logger="app.services.k3s_crypto"):
        result = decrypt_node_token(legacy_b64)

    assert result == "legacy node token"
    assert any("legacy" in r.message for r in caplog.records)
