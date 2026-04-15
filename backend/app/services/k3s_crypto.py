import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import get_settings


def _get_key() -> bytes:
    hex_key = get_settings().k3s_kubeconfig_encryption_key
    if not hex_key or len(hex_key) != 64:
        raise ValueError(
            "k3s_kubeconfig_encryption_key must be 64 hex characters (32 bytes). "
            "Generate with: openssl rand -hex 32"
        )
    return bytes.fromhex(hex_key)


def _get_notion_key() -> bytes:
    s = get_settings()
    hex_key = s.notion_config_encryption_key or s.k3s_kubeconfig_encryption_key
    if not hex_key or len(hex_key) != 64:
        raise ValueError(
            "notion_config_encryption_key (or k3s_kubeconfig_encryption_key) must be "
            "64 hex characters (32 bytes). Generate with: openssl rand -hex 32"
        )
    return bytes.fromhex(hex_key)


def _aes_encrypt(key: bytes, plaintext: str) -> str:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def _aes_decrypt(key: bytes, ciphertext_b64: str) -> str:
    raw = base64.b64decode(ciphertext_b64)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()


def encrypt_kubeconfig(plaintext: str) -> str:
    """Encrypt kubeconfig YAML string with AES-256-GCM.
    Returns base64(nonce + ciphertext) string.
    """
    return _aes_encrypt(_get_key(), plaintext)


def decrypt_kubeconfig(ciphertext_b64: str) -> str:
    """Decrypt base64(nonce + ciphertext) string back to kubeconfig YAML."""
    return _aes_decrypt(_get_key(), ciphertext_b64)


def encrypt_notion_config(plaintext: str) -> str:
    """Encrypt Notion API key with AES-256-GCM."""
    return _aes_encrypt(_get_notion_key(), plaintext)


def decrypt_notion_config(ciphertext_b64: str) -> str:
    """Decrypt Notion API key."""
    return _aes_decrypt(_get_notion_key(), ciphertext_b64)
