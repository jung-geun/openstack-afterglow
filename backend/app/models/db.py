"""SQLAlchemy ORM 모델 — k3s 클러스터 영속화."""

from datetime import datetime, timezone

from sqlalchemy import (
    CHAR, INT, TEXT, VARCHAR,
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
