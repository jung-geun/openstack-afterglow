"""빌트인 AI 채팅 SQLAlchemy ORM 모델 (마이그레이션 026_chat_builtin.sql 대응).

프로바이더/모델 카탈로그, 대화/메시지, 사용량 원장, 사용자 지갑(크레딧·월 쿼터).
모든 사용자 리소스(chat_conversations 등)는 project_id + user_id 를 보유해 소유권 검증 대상.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    CHAR,
    INT,
    JSON,
    TEXT,
    VARCHAR,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class LlmProvider(Base):
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    api_base: Mapped[str | None] = mapped_column(VARCHAR(255))
    # AES-256-GCM(k3s_kubeconfig_encryption_key, 도메인 llm_provider_key) 암호화 상태로 저장
    encrypted_api_key: Mapped[str | None] = mapped_column(TEXT)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    margin_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("1.0"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    models: Mapped[list["LlmModel"]] = relationship("LlmModel", back_populates="provider", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("name", name="uq_llm_providers_name"),)


class LlmModel(Base):
    __tablename__ = "llm_models"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False)
    model_name: Mapped[str] = mapped_column(VARCHAR(190), nullable=False)
    display_name: Mapped[str | None] = mapped_column(VARCHAR(150))
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    # 미지정 시 litellm 내장 단가 사용 (override용). 토큰당 USD 단가.
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    provider: Mapped["LlmProvider"] = relationship("LlmProvider", back_populates="models")

    __table_args__ = (
        UniqueConstraint("provider_id", "model_name", name="uq_llm_models_provider_model"),
        Index("idx_llm_models_active", "is_active"),
    )


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    user_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    title: Mapped[str | None] = mapped_column(VARCHAR(255))
    model_name: Mapped[str | None] = mapped_column(VARCHAR(190))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_chat_conversations_owner", "project_id", "user_id"),
        Index("idx_chat_conversations_updated", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # system | user | assistant | tool
    content: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    tool_calls: Mapped[list | None] = mapped_column(JSON)
    token_prompt: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    token_completion: Mapped[int] = mapped_column(INT, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="messages")

    __table_args__ = (Index("idx_chat_messages_conversation", "conversation_id", "created_at"),)


class ChatUsageLog(Base):
    __tablename__ = "chat_usage_logs"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    user_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(CHAR(36))  # 대화 삭제 후에도 원장 보존 — FK 없음
    model_name: Mapped[str] = mapped_column(VARCHAR(190), nullable=False)
    provider: Mapped[str | None] = mapped_column(VARCHAR(100))
    prompt_tokens: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    raw_cost: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False, default=Decimal("0"))
    credited_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"))
    source: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="web")  # web | api
    api_key_id: Mapped[int | None] = mapped_column(BIGINT)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        Index("idx_chat_usage_project_created", "project_id", "created_at"),
        Index("idx_chat_usage_user_created", "user_id", "created_at"),
    )


class UserWallet(Base):
    __tablename__ = "user_wallets"

    user_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    balance_credits: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"))
    max_quota_monthly: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"))
    used_quota_this_month: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False, default=Decimal("0"))
    quota_period_start: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
