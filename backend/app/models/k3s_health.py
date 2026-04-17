"""K3s 클러스터 헬스체크 응답 모델."""

from pydantic import BaseModel


class K3sNodeHealth(BaseModel):
    name: str
    role: str  # "server" | "agent"
    ready: bool
    conditions: list[str] = []  # e.g. ["Ready", "MemoryPressure"]
    kubelet_version: str | None = None


class K3sClusterHealth(BaseModel):
    cluster_id: str
    cluster_name: str
    status: str  # "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "UNREACHABLE" | "UNKNOWN"
    api_server_reachable: bool
    healthz_ok: bool
    nodes: list[K3sNodeHealth] = []
    checked_at: str
    error: str | None = None
    reachability: str  # "direct" | "unreachable"
