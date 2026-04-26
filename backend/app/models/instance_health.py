"""인스턴스 OverlayFS/NFS 헬스체크 모델."""

from pydantic import BaseModel


class ShareHealth(BaseModel):
    name: str
    proto: str  # "CEPHFS" | "NFS" | "NONE"
    mounted: bool
    status: str  # "ok" | "unreachable" | "timeout"


class InstanceHealthReport(BaseModel):
    """VM이 POST /health/report 로 전송하는 raw payload."""

    overlay_mounted: bool
    upper_used_bytes: int = 0
    upper_total_bytes: int = 0
    upper_usage_pct: float = 0.0
    shares: list[ShareHealth] = []
    kernel: str = ""
    uptime_seconds: float = 0.0
    reported_at: str  # ISO 8601


class InstanceHealth(BaseModel):
    """GET /health 응답 — 서버 측 status/warnings 추가."""

    instance_id: str
    status: str  # "healthy" | "warning" | "error" | "stale" | "unknown"
    warnings: list[str] = []
    overlay_mounted: bool = False
    upper_used_bytes: int = 0
    upper_total_bytes: int = 0
    upper_usage_pct: float = 0.0
    shares: list[ShareHealth] = []
    kernel: str = ""
    uptime_seconds: float = 0.0
    reported_at: str | None = None
    checked_at: str | None = None
