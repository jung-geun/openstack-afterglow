"""관리자 공지(announcement) ORM 모델.

공지는 관리자가 전체/특정 프로젝트/특정 유저를 대상으로 발송하며,
사용자별 읽음 상태는 별도 announcement_reads 테이블로 추적한다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BIGINT, BOOLEAN, TEXT, VARCHAR, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Announcement(Base):
    """관리자가 발송하는 공지. target_type='all'|'project'|'user'."""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    created_by_user_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    created_by_username: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    title: Mapped[str] = mapped_column(VARCHAR(200), nullable=False)
    body: Mapped[str] = mapped_column(TEXT, nullable=False)
    severity: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="info")
    target_type: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    target_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)

    __table_args__ = (
        Index("idx_announcements_active_target", "is_active", "target_type", "target_id"),
        Index("idx_announcements_created", "created_at"),
    )


class AnnouncementRead(Base):
    """유저별 공지 읽음 기록. (announcement_id, user_id) 복합 PK."""

    __tablename__ = "announcement_reads"

    announcement_id: Mapped[int] = mapped_column(
        BIGINT, ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
