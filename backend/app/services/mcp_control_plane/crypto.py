"""Strict AEAD protection for server-held MCP application-credential secrets."""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.k3s_crypto import derive_encryption_subkey

_PREFIX = "mcp-ac1:"
_DOMAIN = b"mcp_app_credential"


def _aad(*, grant_id: str, owner_user_id: str, owner_project_id: str) -> bytes:
    """Bind ciphertext to its immutable delegated-grant identity."""
    if not all(
        isinstance(value, str) and value and "\x00" not in value
        for value in (grant_id, owner_user_id, owner_project_id)
    ):
        raise ValueError("MCP credential identity is invalid")
    return b"afterglow-mcp-app-credential-v1\x00" + b"\x00".join(
        value.encode("utf-8") for value in (grant_id, owner_user_id, owner_project_id)
    )


def encrypt_application_credential(secret: str, *, grant_id: str, owner_user_id: str, owner_project_id: str) -> str:
    """Encrypt one Keystone secret with a grant-bound AEAD; no plaintext fallback exists."""
    if not isinstance(secret, str) or not secret:
        raise ValueError("MCP application credential secret is invalid")
    aad = _aad(grant_id=grant_id, owner_user_id=owner_user_id, owner_project_id=owner_project_id)
    nonce = os.urandom(12)
    ciphertext = AESGCM(derive_encryption_subkey(_DOMAIN)).encrypt(nonce, secret.encode("utf-8"), aad)
    return _PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_application_credential(ciphertext: str, *, grant_id: str, owner_user_id: str, owner_project_id: str) -> str:
    """Decrypt only current-format ciphertext bound to exactly the originating grant."""
    if not isinstance(ciphertext, str) or not ciphertext.startswith(_PREFIX):
        raise ValueError("MCP application credential ciphertext is invalid")
    try:
        payload = base64.b64decode(ciphertext[len(_PREFIX) :].encode("ascii"), altchars=b"-_", validate=True)
        if len(payload) < 13:
            raise ValueError("MCP application credential ciphertext is malformed")
        value = AESGCM(derive_encryption_subkey(_DOMAIN)).decrypt(
            payload[:12],
            payload[12:],
            _aad(grant_id=grant_id, owner_user_id=owner_user_id, owner_project_id=owner_project_id),
        )
        secret = value.decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error, InvalidTag) as exc:
        raise ValueError("MCP application credential ciphertext is invalid") from exc
    if not secret:
        raise ValueError("MCP application credential secret is invalid")
    return secret
