"""WireGuard VPN 게이트웨이 Pydantic 스키마 + 보안 validator.

cloud-init/쉘로 흐르는 모든 값(client name·CIDR·dns 등)은 화이트리스트 정규식으로
검증한다. 개행·쉘 메타문자를 거부해 YAML 구조 파괴(임의 write_files/runcmd 주입)를
막는다. 참조: app/services/cloudinit.py:_validate_cloudinit_inputs,
app/models/k3s.py:_NAME_RE.
"""

import ipaddress
import re

from pydantic import BaseModel, Field, field_validator

# 이름: 영문/숫자로 시작, 영문·숫자·하이픈·언더스코어만 허용 (k3s CreateK3sClusterRequest와 동일 관례)
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")

# WireGuard X25519 키는 base64 44자(32바이트 + 패딩 '='). 표준 base64 알파벳만 허용.
_WG_KEY_RE = re.compile(r"^[A-Za-z0-9+/]{42,43}=\Z")

# DNS: 호스트네임 또는 IPv4/IPv6 (콤마 구분 최대 2개). 쉘/YAML 메타문자 차단.
_DNS_HOST_RE = re.compile(r"^[A-Za-z0-9.:_-]{1,253}$")


class VpnServerCreateRequest(BaseModel):
    """VPN 서버 생성 요청."""

    name: str = Field(default="")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        import uuid

        if not v.strip():
            return f"vpn-{uuid.uuid4().hex[:8]}"
        if not _NAME_RE.match(v):
            raise ValueError("이름은 영문/숫자로 시작하고, 영문·숫자·하이픈·언더스코어만 허용됩니다 (최대 63자)")
        return v


class VpnServerInfo(BaseModel):
    """VPN 서버 상세/목록 응답."""

    id: str
    project_id: str
    name: str
    status: str
    status_reason: str | None = None
    server_vm_id: str | None = None
    endpoint_ip: str | None = None
    listen_port: int
    tunnel_cidr: str
    dns: str | None = None
    mtu: int | None = None
    server_public_key: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Redis 최신 상태 병합 (에이전트가 마지막으로 보고한 시각/피어 수)
    last_status_reported_at: str | None = None
    peer_count: int | None = None


class VpnClientCreateRequest(BaseModel):
    """VPN 클라이언트(peer) 발급 요청."""

    name: str
    allowed_ips: list[str] | None = Field(default=None, max_length=20)
    dns: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError("이름은 영문/숫자로 시작하고, 영문·숫자·하이픈·언더스코어만 허용됩니다 (최대 63자)")
        return v

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        validated: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError("allowed_ips 의 각 항목은 문자열이어야 합니다")
            try:
                net = ipaddress.ip_network(raw, strict=False)
            except (ValueError, TypeError) as e:
                raise ValueError(f"allowed_ips '{raw}' 가 유효한 CIDR 이 아닙니다: {e}") from e
            validated.append(str(net))
        return validated

    @field_validator("dns")
    @classmethod
    def validate_dns(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        for host in v.split(","):
            host = host.strip()
            if not host or not _DNS_HOST_RE.match(host):
                raise ValueError(f"dns 값 '{v}' 형식이 유효하지 않습니다")
        return v


class VpnClientUpdateRequest(BaseModel):
    """VPN 클라이언트 수정 요청 (enable/disable, 이름 변경)."""

    name: str | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _NAME_RE.match(v):
            raise ValueError("이름은 영문/숫자로 시작하고, 영문·숫자·하이픈·언더스코어만 허용됩니다 (최대 63자)")
        return v


class VpnClientInfo(BaseModel):
    """VPN 클라이언트 목록/상세 응답."""

    id: str
    server_id: str
    project_id: str
    name: str
    enabled: bool
    public_key: str
    tunnel_ip: str
    allowed_ips: list[str] = []
    dns: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # Redis 상태 병합
    online: bool | None = None
    last_handshake_at: str | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None


class VpnClientCreateResponse(VpnClientInfo):
    """클라이언트 발급 직후 1회 응답 — 평문 .conf 를 포함한다."""

    tunnel_conf: str


# ---------------------------------------------------------------------------
# 에이전트(베어러 토큰) 대면 스키마
# ---------------------------------------------------------------------------


class VpnAgentRegisterRequest(BaseModel):
    """에이전트가 부팅 후 서버 public key를 보고."""

    public_key: str
    listen_port_confirm: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        if not _WG_KEY_RE.match(v):
            raise ValueError("public_key 형식이 유효하지 않습니다 (WireGuard base64 키가 아님)")
        return v


class VpnAgentPeerState(BaseModel):
    """에이전트가 보고하는 개별 peer 상태 (wg show dump 파싱 결과)."""

    public_key: str
    last_handshake_at: str | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        if not _WG_KEY_RE.match(v):
            raise ValueError("public_key 형식이 유효하지 않습니다 (WireGuard base64 키가 아님)")
        return v


class VpnAgentStatusReport(BaseModel):
    """에이전트가 주기적으로 POST하는 wg show 상태."""

    peers: list[VpnAgentPeerState] = Field(default_factory=list, max_length=1000)
    reported_at: str | None = None


class VpnAgentDesiredStatePeer(BaseModel):
    public_key: str
    preshared_key: str | None = None
    allowed_ips: list[str]
    enabled: bool = True


class VpnAgentDesiredState(BaseModel):
    """에이전트가 폴링하는 desired-state 응답."""

    listen_port: int
    tunnel_cidr: str
    peers: list[VpnAgentDesiredStatePeer] = []
