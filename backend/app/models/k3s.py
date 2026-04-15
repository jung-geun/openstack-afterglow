from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re

_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$')


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
    cluster_id: Optional[str] = None
    error: Optional[str] = None


class CreateK3sClusterRequest(BaseModel):
    name: str
    agent_count: int = Field(default=1, ge=0, le=10)
    agent_flavor_id: Optional[str] = None
    network_id: Optional[str] = None
    key_name: Optional[str] = None

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
    status_reason: Optional[str] = None
    server_vm_id: Optional[str] = None
    agent_vm_ids: list[str] = []
    agent_count: int = 0
    api_address: Optional[str] = None
    server_ip: Optional[str] = None
    network_id: Optional[str] = None
    key_name: Optional[str] = None
    k3s_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ScaleK3sClusterRequest(BaseModel):
    agent_count: int = Field(ge=0, le=10)


class K3sCallbackRequest(BaseModel):
    token: str
    success: bool
    kubeconfig: Optional[str] = None
    node_token: Optional[str] = None
    server_ip: Optional[str] = None
    error: Optional[str] = None
