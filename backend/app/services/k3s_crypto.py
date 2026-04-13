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


def encrypt_kubeconfig(plaintext: str) -> str:
    """Encrypt kubeconfig YAML string with AES-256-GCM.
    Returns base64(nonce + ciphertext) string.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_kubeconfig(ciphertext_b64: str) -> str:
    """Decrypt base64(nonce + ciphertext) string back to kubeconfig YAML."""
    key = _get_key()
    raw = base64.b64decode(ciphertext_b64)
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None).decode()
