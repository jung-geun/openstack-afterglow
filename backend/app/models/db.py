"""SQLAlchemy ORM 모델 — k3s 클러스터 및 Notion 설정 영속화."""

from datetime import datetime, timezone

from sqlalchemy import (
    BOOLEAN, CHAR, INT, TEXT, VARCHAR,
    DateTime, ForeignKey, Index, String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class K3sCluster(Base):
    __tablename__ = "k3s_clusters"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(VARCHAR(63), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    status_reason: Mapped[str | None] = mapped_column(TEXT)

    # OpenStack 리소스 ID
    server_vm_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    server_flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    agent_flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    network_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    security_group_id: Mapped[str | None] = mapped_column(VARCHAR(64))

    # k3s 정보
    server_ip: Mapped[str | None] = mapped_column(VARCHAR(45))
    api_address: Mapped[str | None] = mapped_column(VARCHAR(255))
    k3s_version: Mapped[str | None] = mapped_column(VARCHAR(32))
    node_token: Mapped[str | None] = mapped_column(VARCHAR(512))  # 에이전트 join용

    # SSH / 접근
    key_name: Mapped[str | None] = mapped_column(VARCHAR(255))
    ssh_public_key: Mapped[str | None] = mapped_column(TEXT)

    # kubeconfig (AES-256-GCM 암호화 상태로 저장)
    kubeconfig_encrypted: Mapped[str | None] = mapped_column(TEXT)

    # 생성자 정보
    created_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64), index=True)
    created_by_username: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 설정
    agent_count: Mapped[int] = mapped_column(INT, nullable=False, default=0)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # 관계
    agent_vms: Mapped[list["K3sAgentVM"]] = relationship(
        "K3sAgentVM", back_populates="cluster", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_k3s_cluster_project_created", "project_id", "created_at"),
    )


class K3sAgentVM(Base):
    __tablename__ = "k3s_agent_vms"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    cluster_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("k3s_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vm_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(VARCHAR(255))
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    cluster: Mapped["K3sCluster"] = relationship("K3sCluster", back_populates="agent_vms")


class NotionConfig(Base):
    """Notion 연동 설정 (싱글톤, id=1 고정). API key는 AES-256-GCM 암호화 저장."""

    __tablename__ = "notion_config"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)

    # 민감 정보 — AES-256-GCM 암호화
    api_key_encrypted: Mapped[str] = mapped_column(TEXT, nullable=False)

    # 데이터베이스 ID
    database_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    users_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    hypervisors_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    gpu_spec_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))

    # 동기화 설정
    enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(INT, nullable=False, default=5)

    # 마지막 동기화 시각
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hypervisors_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gpu_spec_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
