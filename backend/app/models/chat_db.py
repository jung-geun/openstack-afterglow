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
    # litellm custom_llm_provider (openai|anthropic|gemini|vertex_ai|azure|bedrock|ollama|...)
    provider_type: Mapped[str] = mapped_column(VARCHAR(40), nullable=False, default="openai")
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
    # 대화 제목 자동 요약에 쓸 모델. 앱 레벨에서 최대 1개만 True 로 유지(set_title_model).
    is_title_model: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
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
    # AES-256-GCM(도메인 chat_content) 암호문. 첫 메시지 요약 제목도 채팅 내용이라 암호화. TEXT(암호문 길이).
    title: Mapped[str | None] = mapped_column(TEXT)
    model_name: Mapped[str | None] = mapped_column(VARCHAR(190))
    # 버전 트리에서 현재 보이는 리프 메시지. 렌더 경로 = active_leaf → parent 역추적.
    active_leaf_id: Mapped[int | None] = mapped_column(BIGINT)
    # 분기(fork) 출처: 이 대화가 어느 대화의 어느 메시지에서 갈라졌는지(감사·표시용).
    parent_conversation_id: Mapped[str | None] = mapped_column(CHAR(36))
    forked_from_message_id: Mapped[int | None] = mapped_column(BIGINT)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_chat_conversations_owner", "project_id", "user_id"),
        Index("idx_chat_conversations_user_updated", "user_id", "updated_at"),  # 사용자별 목록(프로젝트 무관)
        Index("idx_chat_conversations_updated", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)  # system | user | assistant | tool
    # 버전 트리 부모 메시지 id. 같은 parent_id 를 공유하는 형제 = 재생성 버전들. 루트는 NULL.
    parent_id: Mapped[int | None] = mapped_column(BIGINT)
    # AES-256-GCM(도메인 chat_content) 암호문 저장. 읽을 때 decrypt_chat_content 로 복호화.
    content: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    # 툴 호출 기록(JSON)을 직렬화 후 암호화한 문자열. 평문 JSON 컬럼이 아님(암호화 도입).
    tool_calls: Mapped[str | None] = mapped_column(MEDIUMTEXT)
    token_prompt: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    token_completion: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    # 재생성 시 어떤 모델로 생성했는지(형제 버전 구분·표시용). 미지정 시 대화 기본 모델.
    model_name: Mapped[str | None] = mapped_column(VARCHAR(190))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_messages_conversation", "conversation_id", "created_at"),
        Index("idx_chat_messages_parent", "parent_id"),
    )


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


class ChatMcpServer(Base):
    """MCP 서버 (등록·관리 전용 — 실행은 langchain-mcp-adapters 핀 이동 후). scope: global|user."""

    __tablename__ = "chat_mcp_servers"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="user")
    owner_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    owner_project_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    transport: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="http")  # http|sse|stdio
    url: Mapped[str | None] = mapped_column(VARCHAR(500))
    command: Mapped[str | None] = mapped_column(VARCHAR(500))
    headers: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_chat_mcp_scope", "scope"),
        Index("idx_chat_mcp_owner", "owner_user_id"),
    )


class ChatCustomTool(Base):
    """커스텀 HTTP 툴 (백엔드가 SSRF 가드 후 대리 호출). scope: global|user."""

    __tablename__ = "chat_custom_tools"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="user")
    owner_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    owner_project_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)  # 영숫자/언더스코어
    description: Mapped[str] = mapped_column(VARCHAR(500), nullable=False)
    method: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="GET")  # GET|POST
    url: Mapped[str] = mapped_column(VARCHAR(500), nullable=False)
    params_schema: Mapped[dict | None] = mapped_column(JSON)
    timeout_seconds: Mapped[int] = mapped_column(INT, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_chat_tool_scope", "scope"),
        Index("idx_chat_tool_owner", "owner_user_id"),
    )
