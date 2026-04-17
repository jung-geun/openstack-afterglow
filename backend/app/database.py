"""SQLAlchemy async 데이터베이스 연결 관리.

설정: config.toml [database] 섹션 또는 DATABASE_URL 환경변수.
url이 비어있으면 DB 연결 없이 Redis 폴백으로 동작.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

_logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


class Base(DeclarativeBase):
    pass


def init_db(database_url: str, pool_size: int = 5, max_overflow: int = 10) -> None:
    """앱 시작 시 호출. engine과 session factory를 초기화."""
    global _engine, _session_factory
    if not database_url:
        _logger.info("database.url 미설정 — DB 없이 Redis 폴백으로 동작합니다")
        return

    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    _logger.info("데이터베이스 연결 초기화 완료: %s", _mask_url(database_url))


def is_db_available() -> bool:
    """DB 연결이 초기화되어 있으면 True."""
    return _engine is not None


async def create_tables() -> None:
    """ORM 모델 기반으로 테이블 자동 생성 (auto_create_tables=true 시 호출)."""
    if _engine is None:
        return
    from app.models.db import Base as _ModelBase  # noqa: F401 — side effect: 모델 등록

    async with _engine.begin() as conn:
        await conn.run_sync(_ModelBase.metadata.create_all)

    # 기존 테이블에 soft-delete 컬럼 추가 (없는 경우에만)
    async with _engine.begin() as conn:
        for col, col_def in [
            ("deleted_at", "DATETIME(6)"),
            ("deleted_by_user_id", "VARCHAR(64)"),
            ("deleted_reason", "VARCHAR(255)"),
        ]:
            try:
                await conn.exec_driver_sql(f"ALTER TABLE k3s_clusters ADD COLUMN {col} {col_def} DEFAULT NULL")
            except Exception:
                pass  # 이미 존재하면 무시

        # OCCM 활성화 플래그 추가 (없는 경우에만)
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE k3s_clusters ADD COLUMN occm_enabled BOOLEAN NOT NULL DEFAULT FALSE"
            )
        except Exception:
            pass  # 이미 존재하면 무시

        # 플러그인 목록 JSON 컬럼 추가 (없는 경우에만)
        try:
            await conn.exec_driver_sql("ALTER TABLE k3s_clusters ADD COLUMN plugins_enabled JSON DEFAULT NULL")
        except Exception:
            pass  # 이미 존재하면 무시

    _logger.info("데이터베이스 테이블 생성/확인 완료")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends용 세션 제너레이터."""
    if _session_factory is None:
        raise RuntimeError("DB가 초기화되지 않았습니다")
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker | None:
    return _session_factory


async def close_db() -> None:
    """앱 종료 시 엔진 정리."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        _logger.info("데이터베이스 연결 종료")


def _mask_url(url: str) -> str:
    """비밀번호 마스킹 (로그용)."""
    try:
        from urllib.parse import urlparse, urlunparse

        p = urlparse(url)
        if p.password:
            masked = p._replace(netloc=f"{p.username}:***@{p.hostname}:{p.port}")
            return urlunparse(masked)
    except Exception:
        pass
    return url
