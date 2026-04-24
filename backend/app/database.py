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

        # GPU quota 테이블 생성 (없는 경우에만)
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS gpu_quotas ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "project_id VARCHAR(64) NOT NULL,"
                "gpu_type VARCHAR(64) NOT NULL,"
                "`limit` INT NOT NULL DEFAULT -1,"
                "created_at DATETIME(6) NOT NULL,"
                "updated_at DATETIME(6) NOT NULL,"
                "UNIQUE KEY idx_gpu_quota_project_type (project_id, gpu_type),"
                "KEY ix_gpu_quotas_project_id (project_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass  # 이미 존재하면 무시

        # API LB 관련 컬럼 추가 (없는 경우에만)
        for col, col_def in [
            ("api_lb_id", "VARCHAR(64) DEFAULT NULL"),
            ("api_lb_pool_id", "VARCHAR(64) DEFAULT NULL"),
            ("api_fip_id", "VARCHAR(64) DEFAULT NULL"),
            ("api_fip_address", "VARCHAR(45) DEFAULT NULL"),
            ("os_type", "VARCHAR(10) NOT NULL DEFAULT 'ubuntu'"),
        ]:
            try:
                await conn.exec_driver_sql(f"ALTER TABLE k3s_clusters ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # 이미 존재하면 무시

        # 프로젝트 기본 네트워크 테이블 생성 (없는 경우에만)
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS project_default_networks ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "project_id VARCHAR(64) NOT NULL,"
                "network_id VARCHAR(64) NOT NULL,"
                "subnet_id VARCHAR(64) DEFAULT NULL,"
                "router_id VARCHAR(64) DEFAULT NULL,"
                "auto_created BOOLEAN NOT NULL DEFAULT TRUE,"
                "created_at DATETIME(6) NOT NULL,"
                "updated_at DATETIME(6) DEFAULT NULL,"
                "UNIQUE KEY uq_project_default_networks_project_id (project_id),"
                "KEY ix_project_default_networks_project_id (project_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass  # 이미 존재하면 무시

        # Union Mount 레이어 시스템 테이블 (없는 경우에만)
        # union_layers: 부모 자기참조 FK가 있어 먼저 생성
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS union_layers ("
                "id VARCHAR(71) NOT NULL PRIMARY KEY,"
                "name VARCHAR(128) NOT NULL,"
                "version VARCHAR(64) NOT NULL,"
                "created_at DATETIME(6) NOT NULL,"
                "created_by VARCHAR(128) NOT NULL,"
                "sealed BOOLEAN NOT NULL DEFAULT FALSE,"
                "parent_id VARCHAR(71) DEFAULT NULL,"
                "ubuntu_base VARCHAR(255) DEFAULT NULL,"
                "build_recipe JSON NOT NULL,"
                "installed_packages JSON NOT NULL,"
                "content_hash VARCHAR(71) NOT NULL,"
                "size_bytes BIGINT DEFAULT NULL,"
                "file_count INT DEFAULT NULL,"
                "KEY idx_union_layers_name_version (name, version),"
                "KEY idx_union_layers_parent (parent_id),"
                "CONSTRAINT fk_union_layers_parent FOREIGN KEY (parent_id)"
                "  REFERENCES union_layers(id) ON DELETE RESTRICT"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass  # 이미 존재하면 무시

        # union_layers 컬럼 마이그레이션 (신규 컬럼 추가)
        for _col_sql in [
            "ALTER TABLE union_layers ADD COLUMN project_id VARCHAR(64) DEFAULT NULL",
            "ALTER TABLE union_layers ADD COLUMN sealed_at DATETIME(6) DEFAULT NULL",
            "ALTER TABLE union_layers ADD INDEX idx_union_layers_project (project_id)",
        ]:
            try:
                await conn.exec_driver_sql(_col_sql)
            except Exception:
                pass  # 이미 존재하면 무시

        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS union_templates ("
                "name VARCHAR(128) NOT NULL,"
                "version INT NOT NULL,"
                "created_at DATETIME(6) NOT NULL,"
                "created_by VARCHAR(128) NOT NULL,"
                "parent_version INT DEFAULT NULL,"
                "ubuntu_base VARCHAR(255) NOT NULL,"
                "leaf_layer_id VARCHAR(71) NOT NULL,"
                "note TEXT DEFAULT NULL,"
                "PRIMARY KEY (name, version),"
                "KEY idx_union_templates_leaf (leaf_layer_id),"
                "CONSTRAINT fk_union_templates_leaf FOREIGN KEY (leaf_layer_id)"
                "  REFERENCES union_layers(id) ON DELETE RESTRICT"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass

        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS union_user_mounts ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "user_id VARCHAR(128) NOT NULL,"
                "vm_hostname VARCHAR(255) NOT NULL,"
                "leaf_layer_id VARCHAR(71) NOT NULL,"
                "mounted_at DATETIME(6) NOT NULL,"
                "unmounted_at DATETIME(6) DEFAULT NULL,"
                "KEY idx_union_user_mounts_user (user_id),"
                "KEY idx_union_user_mounts_leaf (leaf_layer_id),"
                "CONSTRAINT fk_union_user_mounts_leaf FOREIGN KEY (leaf_layer_id)"
                "  REFERENCES union_layers(id) ON DELETE RESTRICT"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass

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
