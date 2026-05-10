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


class OrphanShareInfo(BaseModel):
    """프로젝트가 사라진 Manila share."""

    id: str
    name: str | None = None
    size_gb: int
    project_id: str | None = None
    status: str
    created_at: str | None = None
    age_days: int
    snapshot_count: int = 0


class OrphanSecurityGroupInfo(BaseModel):
    """afterglow가 자동 생성했으나 어떤 port에도 attach 안 된 Security Group."""

    id: str
    name: str
    description: str | None = None
    project_id: str | None = None
    created_at: str | None = None
    age_days: int


class OrphanScanResponse(BaseModel):
    """orphan 검색 응답."""

    floating_ips: list[OrphanFipInfo]
    volumes: list[OrphanVolumeInfo]
    manila_shares: list[OrphanShareInfo] = []
    security_groups: list[OrphanSecurityGroupInfo] = []


class OrphanCleanupRequest(BaseModel):
    """orphan 일괄 정리 요청."""

    kind: Literal["floating_ip", "volume", "manila_share", "security_group"]
    ids: list[str] = Field(min_length=1)


class OrphanCleanupResponse(BaseModel):
    """orphan 정리 결과 — deleted/failed 분리."""

    deleted: list[str]
    failed: list[dict]  # [{"id": "...", "error": "..."}]
