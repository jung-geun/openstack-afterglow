import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

# 버전 접두사: v2: = AAD 바인딩 활성화, 접두사 없음 = 레거시(AAD 없음)
_V2_PREFIX = "v2:"


def _get_key() -> bytes:
    hex_key = get_settings().k3s_kubeconfig_encryption_key
    if not hex_key or len(hex_key) != 64:
        raise ValueError(
            "k3s_kubeconfig_encryption_key must be 64 hex characters (32 bytes). Generate with: openssl rand -hex 32"
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


def _aes_encrypt(key: bytes, plaintext: str, aad: bytes | None = None) -> str:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), aad)
    b64 = base64.b64encode(nonce + ct).decode()
    return (_V2_PREFIX + b64) if aad is not None else b64


def _aes_decrypt(key: bytes, ciphertext_b64: str, aad: bytes | None = None) -> str:
    """복호화. v2: 접두사가 있으면 AAD를 사용하고, 없으면 레거시(AAD=None)로 폴백."""
    if ciphertext_b64.startswith(_V2_PREFIX):
        raw = base64.b64decode(ciphertext_b64[len(_V2_PREFIX) :])
        effective_aad = aad
    else:
        raw = base64.b64decode(ciphertext_b64)
        effective_aad = None  # 레거시 레코드: AAD 없이 복호화
    nonce, ct = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, effective_aad).decode()


def encrypt_kubeconfig(plaintext: str) -> str:
    """Encrypt kubeconfig YAML string with AES-256-GCM (AAD-bound).
    Returns v2:<base64(nonce + ciphertext)> string.
    """
    return _aes_encrypt(_get_key(), plaintext, aad=b"kubeconfig")


def decrypt_kubeconfig(ciphertext_b64: str) -> str:
    """Decrypt kubeconfig. Handles legacy (no AAD) and v2 (AAD-bound) ciphertexts."""
    return _aes_decrypt(_get_key(), ciphertext_b64, aad=b"kubeconfig")


def encrypt_node_token(plaintext: str) -> str:
    """Encrypt k3s node token with AES-256-GCM (AAD-bound)."""
    return _aes_encrypt(_get_key(), plaintext, aad=b"node_token")


def decrypt_node_token(ciphertext_b64: str) -> str:
    """Decrypt k3s node token. Handles legacy and v2 ciphertexts."""
    return _aes_decrypt(_get_key(), ciphertext_b64, aad=b"node_token")


def encrypt_notion_config(plaintext: str) -> str:
    """Encrypt Notion API key with AES-256-GCM (AAD-bound)."""
    return _aes_encrypt(_get_notion_key(), plaintext, aad=b"notion_config")


def decrypt_notion_config(ciphertext_b64: str) -> str:
    """Decrypt Notion API key. Handles legacy and v2 ciphertexts."""
    return _aes_decrypt(_get_notion_key(), ciphertext_b64, aad=b"notion_config")


def encrypt_manager_password(plaintext: str) -> str:
    """Encrypt per-project cluster manager user password with AES-256-GCM (AAD-bound)."""
    return _aes_encrypt(_get_key(), plaintext, aad=b"manager_password")


def decrypt_manager_password(ciphertext_b64: str) -> str:
    """Decrypt cluster manager user password."""
    return _aes_decrypt(_get_key(), ciphertext_b64, aad=b"manager_password")
