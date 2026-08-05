"""k3s 비밀 데이터 암호화 — AES-256-GCM + HKDF sub-key 도메인 분리.

ciphertext 버전:
- v3:  HKDF-SHA256 으로 마스터키 → 도메인별 sub-key 파생 후 암호화 (현재 권장)
- v2:  마스터키 그대로 사용, AAD = 도메인 (이전 — deprecated)
- (no prefix): 마스터키 그대로 사용, AAD 없음 (legacy — deprecated)

복호화는 v3 → v2 → legacy 순으로 fallback. v2/legacy 는 deprecation warning
로그 1회 기록 후 다음 PR 에서 제거 예정. 마이그레이션 스크립트로 batch
re-encrypt 권장.
"""

import logging

from afterglow_crypto import aesgcm

from app.config import get_settings

_logger = logging.getLogger(__name__)

_V3_PREFIX = aesgcm._V3_PREFIX
_V2_PREFIX = aesgcm._V2_PREFIX

# 도메인 라벨 — encrypt/decrypt 가 같은 값을 써야 함
_DOMAIN_KUBECONFIG = b"kubeconfig"
_DOMAIN_NODE_TOKEN = b"node_token"
_DOMAIN_NOTION = b"notion_config"
_DOMAIN_MANAGER_PW = b"manager_password"
_DOMAIN_LLM_PROVIDER_KEY = b"llm_provider_key"
_DOMAIN_CHAT_CONTENT = b"chat_content"
_DOMAIN_VM_CLOUD_INIT = b"vm_cloud_init"

# Compatibility aliases
_derive_subkey = aesgcm._derive_subkey
_warn_legacy_once = aesgcm._warn_legacy_once
_aes_encrypt_v3 = aesgcm.encrypt
_aes_decrypt = aesgcm.decrypt
_LEGACY_WARNED = aesgcm._LEGACY_WARNED


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


def derive_encryption_subkey(domain: bytes) -> bytes:
    """Return an AES-256 sub-key for a non-empty application encryption domain."""
    return aesgcm.derive_encryption_subkey(_get_key(), domain)


def encrypt_kubeconfig(plaintext: str) -> str:
    """Encrypt kubeconfig YAML string with AES-256-GCM + HKDF sub-key (v3)."""
    return aesgcm.encrypt(_get_key(), _DOMAIN_KUBECONFIG, plaintext)


def decrypt_kubeconfig(ciphertext_b64: str) -> str:
    """Decrypt kubeconfig — v3/v2/legacy 모두 처리."""
    return aesgcm.decrypt(_get_key(), _DOMAIN_KUBECONFIG, ciphertext_b64)


def encrypt_node_token(plaintext: str) -> str:
    """Encrypt k3s node token (v3)."""
    return aesgcm.encrypt(_get_key(), _DOMAIN_NODE_TOKEN, plaintext)


def decrypt_node_token(ciphertext_b64: str) -> str:
    """Decrypt k3s node token — v3/v2/legacy 모두 처리."""
    return aesgcm.decrypt(_get_key(), _DOMAIN_NODE_TOKEN, ciphertext_b64)


def encrypt_notion_config(plaintext: str) -> str:
    """Encrypt Notion API key (v3)."""
    return aesgcm.encrypt(_get_notion_key(), _DOMAIN_NOTION, plaintext)


def decrypt_notion_config(ciphertext_b64: str) -> str:
    """Decrypt Notion API key — v3/v2/legacy 모두 처리."""
    return aesgcm.decrypt(_get_notion_key(), _DOMAIN_NOTION, ciphertext_b64)


def encrypt_manager_password(plaintext: str) -> str:
    """Encrypt per-project cluster manager user password (v3)."""
    return aesgcm.encrypt(_get_key(), _DOMAIN_MANAGER_PW, plaintext)


def decrypt_manager_password(ciphertext_b64: str) -> str:
    """Decrypt cluster manager user password — v3/v2/legacy 모두 처리."""
    return aesgcm.decrypt(_get_key(), _DOMAIN_MANAGER_PW, ciphertext_b64)


def encrypt_llm_provider_key(plaintext: str) -> str:
    """Encrypt 빌트인 AI 채팅 LLM 프로바이더 API 키 (v3).

    마스터키는 기존 k3s_kubeconfig_encryption_key 를 재사용한다(신규 시크릿 불필요).
    도메인 분리로 kubeconfig/node_token 등 다른 도메인 ciphertext와 교차 복호화되지 않는다.
    """
    return aesgcm.encrypt(_get_key(), _DOMAIN_LLM_PROVIDER_KEY, plaintext)


def decrypt_llm_provider_key(ciphertext_b64: str) -> str:
    """Decrypt LLM 프로바이더 API 키 — v3/v2/legacy 모두 처리."""
    return aesgcm.decrypt(_get_key(), _DOMAIN_LLM_PROVIDER_KEY, ciphertext_b64)


def encrypt_chat_content(plaintext: str) -> str:
    """Encrypt 빌트인 AI 채팅 메시지/툴 기록/제목 (v3).

    마스터키는 기존 k3s_kubeconfig_encryption_key 를 재사용한다(신규 시크릿 불필요).
    """
    return aesgcm.encrypt(_get_key(), _DOMAIN_CHAT_CONTENT, plaintext)


def decrypt_chat_content(ciphertext_b64: str) -> str:
    """Decrypt 채팅 콘텐츠 — v3 만 복호화, prefix 없으면 암호화 이전 평문으로 간주해 그대로 반환.

    ⚠️ 채팅 콘텐츠는 legacy(prefix 없는) *암호문* 시대가 없다(암호화 도입 = v3 부터). 따라서
    prefix 없는 값은 암호화 도입 전에 저장된 *평문*이며, generic _aes_decrypt 의 legacy 경로로
    보내면 평문을 base64/AES-GCM 복호화하려다 깨진다. 평문 passthrough 로 하위호환한다.
    """
    if not ciphertext_b64.startswith(_V3_PREFIX):
        return ciphertext_b64
    return aesgcm.decrypt(_get_key(), _DOMAIN_CHAT_CONTENT, ciphertext_b64)


def encrypt_vm_cloud_init(plaintext: str) -> str:
    """Encrypt a user's reusable VM cloud-init snippet with a dedicated sub-key."""
    return aesgcm.encrypt(_get_key(), _DOMAIN_VM_CLOUD_INIT, plaintext)


def decrypt_vm_cloud_init(ciphertext_b64: str) -> str:
    """Decrypt a user's reusable VM cloud-init snippet."""
    return aesgcm.decrypt(_get_key(), _DOMAIN_VM_CLOUD_INIT, ciphertext_b64)
