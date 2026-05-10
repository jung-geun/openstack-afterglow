"""Admin orphan resource detection — Pydantic 모델."""

from typing import Literal

from pydantic import BaseModel, Field


class OrphanFipInfo(BaseModel):
    """분리(port_id NULL) 상태인 Floating IP."""

    id: str
    address: str
    project_id: str | None = None
    created_at: str | None = None
    age_days: int


class OrphanVolumeInfo(BaseModel):
    """장기 미사용(status=available, attachments=[]) Cinder volume."""

    id: str
    name: str | None = None
    size_gb: int
    project_id: str | None = None
    status: str
    created_at: str | None = None
    age_days: int


class OrphanScanResponse(BaseModel):
    """orphan 검색 응답."""

    floating_ips: list[OrphanFipInfo]
    volumes: list[OrphanVolumeInfo]


class OrphanCleanupRequest(BaseModel):
    """orphan 일괄 정리 요청."""

    kind: Literal["floating_ip", "volume"]
    ids: list[str] = Field(min_length=1)


class OrphanCleanupResponse(BaseModel):
    """orphan 정리 결과 — deleted/failed 분리."""

    deleted: list[str]
    failed: list[dict]  # [{"id": "...", "error": "..."}]
