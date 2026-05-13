import ipaddress
import re
import uuid
from enum import Enum

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")
# k3s server 가 발급하는 node-token 은 영숫자 + : _ + / = . - 만 사용. shell variable 치환을 거치므로
# 임의 메타문자 차단 — callback 단계에서 검증해 cloud-init 단계에서 인젝션을 차단한다.
_NODE_TOKEN_RE = re.compile(r"^[A-Za-z0-9:_+/=.\-]{8,512}$")


class K3sProgressStep(str, Enum):
    SECURITY_GROUP = "security_group"
    SERVER_VOLUME = "server_volume"
    SERVER_CREATING = "server_creating"
    WAITING_CALLBACK = "waiting_callback"
    COMPLETED = "completed"
    FAILED = "failed"
    # 삭제 단계
    DELETE_INIT = "delete_init"
    DELETE_LB_CLEANUP = "delete_lb_cleanup"
    DELETE_APP_CREDENTIAL = "delete_app_credential"
    DELETE_K8S_NODES = "delete_k8s_nodes"
    DELETE_AGENT_VMS = "delete_agent_vms"
    DELETE_SERVER_VM = "delete_server_vm"
    DELETE_SECURITY_GROUP = "delete_security_group"
    DELETE_RECORD = "delete_record"


class K3sProgressMessage(BaseModel):
    step: K3sProgressStep
    progress: int  # 0-100
    message: str
    cluster_id: str | None = None
    error: str | None = None
    elapsed_seconds: float | None = None


_VALID_OS_TYPES = {"ubuntu", "fcos"}


class CreateK3sClusterRequest(BaseModel):
    name: str = ""
    agent_count: int = Field(default=1, ge=0, le=10)
    agent_flavor_id: str | None = None
    network_id: str | None = None
    key_name: str | None = None
    os_type: str = "ubuntu"  # "ubuntu" | "fcos"
    # SSH/K3s API 접근 허용 CIDR (미지정 시 0.0.0.0/0). 형식 검증 + 최대 20개로 quota 폭증 방지.
    allowed_cidrs: list[str] | None = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            return f"k3s-{uuid.uuid4().hex[:8]}"
        if not _NAME_RE.match(v):
            raise ValueError("이름은 영문/숫자로 시작하고, 영문·숫자·하이픈·언더스코어만 허용됩니다 (최대 63자)")
        return v

    @field_validator("os_type")
    @classmethod
    def validate_os_type(cls, v: str) -> str:
        if v not in _VALID_OS_TYPES:
            raise ValueError(f"os_type은 {sorted(_VALID_OS_TYPES)} 중 하나여야 합니다")
        return v

    @field_validator("allowed_cidrs")
    @classmethod
    def validate_allowed_cidrs(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        validated: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                raise ValueError("allowed_cidrs 의 각 항목은 문자열이어야 합니다")
            try:
                # strict=False — 호스트 비트를 0 으로 정규화
                net = ipaddress.ip_network(raw, strict=False)
            except (ValueError, TypeError) as e:
                raise ValueError(f"allowed_cidrs '{raw}' 가 유효한 CIDR 이 아닙니다: {e}") from e
            validated.append(str(net))
        return validated


class K3sClusterInfo(BaseModel):
    id: str
    name: str
    status: str
    status_reason: str | None = None
    server_vm_id: str | None = None
    agent_vm_ids: list[str] = []
    agent_count: int = 0
    api_address: str | None = None
    server_ip: str | None = None
    network_id: str | None = None
    key_name: str | None = None
    k3s_version: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    deleted_by_user_id: str | None = None
    deleted_reason: str | None = None
    occm_enabled: bool = False
    plugins_enabled: dict[str, bool] = {}  # {"occm": true, "cinder_csi": true, ...}
    health_status: str | None = (
        None  # 최신 헬스체크 결과: "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "UNREACHABLE" | "UNKNOWN"
    )
    api_lb_id: str | None = None
    api_fip_id: str | None = None
    api_fip_address: str | None = None
    os_type: str | None = None


class K3sClusterInfoDeleted(K3sClusterInfo):
    """삭제 이력 포함 클러스터 정보."""

    deleted_at: str | None = None
    deleted_by_user_id: str | None = None
    deleted_reason: str | None = None


class ScaleK3sClusterRequest(BaseModel):
    agent_count: int = Field(ge=0, le=10)


class K3sCallbackRequest(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    success: bool
    kubeconfig: str | None = Field(default=None, max_length=65536)
    # node_token 은 agent userdata 의 shell 변수로 들어가므로 메타문자 차단.
    node_token: str | None = Field(default=None, max_length=512)
    server_ip: str | None = Field(default=None, max_length=64)
    error: str | None = Field(default=None, max_length=2048)
    occm_status: str | None = Field(default=None, max_length=64)  # 하위호환 유지 (deprecated)
    plugin_status: dict[str, str | dict] | None = None  # {"occm": {"status": "deployed", "error": ""}}
    secret_cloud_config_status: str | None = Field(default=None, max_length=64)  # "ok" | "failed"

    @field_validator("node_token")
    @classmethod
    def validate_node_token(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _NODE_TOKEN_RE.match(v):
            raise ValueError("node_token 형식이 올바르지 않습니다 (영숫자 + :_+/=.- 만 허용)")
        return v

    @field_validator("server_ip")
    @classmethod
    def validate_server_ip(cls, v: str | None) -> str | None:
        if v is None or not v:
            return v
        try:
            ipaddress.ip_address(v)
        except ValueError as e:
            raise ValueError(f"server_ip '{v}' 가 유효한 IP 주소가 아닙니다") from e
        return v
