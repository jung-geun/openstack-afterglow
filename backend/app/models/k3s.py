import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


class K3sProgressStep(str, Enum):
    SECURITY_GROUP = "security_group"
    SERVER_VOLUME = "server_volume"
    SERVER_CREATING = "server_creating"
    WAITING_CALLBACK = "waiting_callback"
    COMPLETED = "completed"
    FAILED = "failed"


class K3sProgressMessage(BaseModel):
    step: K3sProgressStep
    progress: int  # 0-100
    message: str
    cluster_id: str | None = None
    error: str | None = None


class CreateK3sClusterRequest(BaseModel):
    name: str
    agent_count: int = Field(default=1, ge=0, le=10)
    agent_flavor_id: str | None = None
    network_id: str | None = None
    key_name: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _NAME_RE.match(v):
            raise ValueError("이름은 영문/숫자로 시작하고, 영문·숫자·하이픈·언더스코어만 허용됩니다 (최대 63자)")
        return v


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


class K3sClusterInfoDeleted(K3sClusterInfo):
    """삭제 이력 포함 클러스터 정보."""

    deleted_at: str | None = None
    deleted_by_user_id: str | None = None
    deleted_reason: str | None = None


class ScaleK3sClusterRequest(BaseModel):
    agent_count: int = Field(ge=0, le=10)


class K3sCallbackRequest(BaseModel):
    token: str
    success: bool
    kubeconfig: str | None = None
    node_token: str | None = None
    server_ip: str | None = None
    error: str | None = None
    occm_status: str | None = None  # 하위호환 유지 (deprecated)
    plugin_status: dict[str, str] | None = None  # {"occm": "deployed", "cinder_csi": "failed"}
