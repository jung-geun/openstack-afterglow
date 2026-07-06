"""SQLAlchemy async 데이터베이스 연결 관리.

설정: afterglow.conf/config.toml [database] 섹션 또는 DATABASE_URL 환경변수.
url이 비어있으면 DB 연결 없이 Redis 폴백으로 동작.
"""

import logging
import time
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

# circuit breaker: OperationalError 발생 시 일정 시간 DB 호출 차단
_db_unhealthy_until: float = 0.0
_default_unhealthy_seconds: int = 15


class Base(DeclarativeBase):
    pass


def init_db(
    database_url: str,
    pool_size: int = 5,
    max_overflow: int = 10,
    connect_timeout: int = 10,
    pool_timeout: int = 10,
    unhealthy_seconds: int = 15,
) -> None:
    """앱 시작 시 호출. engine과 session factory를 초기화."""
    global _engine, _session_factory, _default_unhealthy_seconds
    _default_unhealthy_seconds = unhealthy_seconds
    if not database_url:
        _logger.info("database.url 미설정 — DB 없이 Redis 폴백으로 동작합니다")
        return

    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_timeout=pool_timeout,
        pool_recycle=1800,
        connect_args={"connect_timeout": connect_timeout},
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    _logger.info("데이터베이스 연결 초기화 완료: %s", _mask_url(database_url))


def is_db_available() -> bool:
    """DB 연결이 초기화되어 있고 circuit breaker가 열리지 않았으면 True."""
    if _engine is None:
        return False
    if time.time() < _db_unhealthy_until:
        return False
    return True


def mark_db_unhealthy(seconds: int | None = None) -> None:
    """OperationalError 발생 시 호출 — 지정 시간 동안 is_db_available() False 반환.

    seconds=None이면 init_db에서 설정한 기본값(_default_unhealthy_seconds) 사용.
    """
    global _db_unhealthy_until
    duration = seconds if seconds is not None else _default_unhealthy_seconds
    _db_unhealthy_until = time.time() + duration
    _logger.warning("DB circuit breaker 활성화: %d초 동안 DB 호출 차단", duration)


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
            ("plugin_status", "JSON DEFAULT NULL"),
            ("secret_cloud_config_status", "VARCHAR(20) DEFAULT NULL"),
            ("app_credential_id", "VARCHAR(64) DEFAULT NULL"),
        ]:
            try:
                await conn.exec_driver_sql(f"ALTER TABLE k3s_clusters ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # 이미 존재하면 무시

        # Template (PR 1) + Master HA (PR 2) + 인증서 회전 (PR 3-B) 컬럼 (없는 경우에만)
        for col, col_def in [
            ("template_id", "CHAR(36) DEFAULT NULL"),
            ("template_snapshot", "JSON DEFAULT NULL"),
            ("master_count", "INT NOT NULL DEFAULT 1"),
            ("last_rotation_at", "DATETIME(6) DEFAULT NULL"),
            ("last_rotation_initiated_by", "VARCHAR(64) DEFAULT NULL"),
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

        # 프로젝트 관리 사용자 자격 캐시 (k3s Octavia Ingress App Credential 발급용)
        # — keystone.ensure_cluster_manager_user 가 raw SQL 로 read/write
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS project_manager_credentials ("
                "project_id VARCHAR(64) NOT NULL PRIMARY KEY,"
                "user_id VARCHAR(64) NOT NULL,"
                "username VARCHAR(255) NOT NULL,"
                "encrypted_password TEXT NOT NULL,"
                "created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                "updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),"
                "KEY ix_project_manager_credentials_user_id (user_id)"
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
            "ALTER TABLE union_layers ADD COLUMN license_type VARCHAR(64) DEFAULT NULL",
            "ALTER TABLE union_layers ADD COLUMN max_concurrent_mounts INT DEFAULT NULL",
            "ALTER TABLE union_layers ADD COLUMN parent_ids JSON DEFAULT NULL",
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

        # library_builds 에 ephemeral 빌드 컬럼 추가 (없는 경우에만)
        for _col_sql in [
            "ALTER TABLE library_builds ADD COLUMN recipe_id INT DEFAULT NULL",
            "ALTER TABLE library_builds ADD COLUMN port_id VARCHAR(64) DEFAULT NULL",
            "ALTER TABLE library_builds ADD COLUMN build_token CHAR(32) DEFAULT NULL",
            "ALTER TABLE library_builds ADD UNIQUE KEY uq_library_builds_token (build_token)",
            "ALTER TABLE library_builds ADD COLUMN console_log_excerpt TEXT DEFAULT NULL",
            "ALTER TABLE library_builds ADD COLUMN cloud_init_status VARCHAR(20) DEFAULT NULL",
        ]:
            try:
                await conn.exec_driver_sql(_col_sql)
            except Exception:
                pass  # 이미 존재하면 무시

        # admin squashfs layer workflow metadata columns (019/020, 없는 경우에만)
        for _col_sql in [
            "ALTER TABLE layer_builds ADD COLUMN apt_packages JSON NULL AFTER pip_packages",
            ("ALTER TABLE layer_artifacts ADD COLUMN apt_packages JSON NULL AFTER pip_packages"),
            (
                "ALTER TABLE layer_builds ADD COLUMN ubuntu_base VARCHAR(255) NOT NULL "
                "DEFAULT 'ubuntu-24.04-server-2026-04-15' AFTER apt_packages"
            ),
            (
                "ALTER TABLE layer_artifacts ADD COLUMN ubuntu_base VARCHAR(255) NOT NULL "
                "DEFAULT 'ubuntu-24.04-server-2026-04-15' AFTER apt_packages"
            ),
        ]:
            try:
                await conn.exec_driver_sql(_col_sql)
            except Exception:
                pass  # 이미 존재하면 무시

        # Glance base image fingerprints + Dockerfile import jobs (021, 없는 경우에만)
        for _table in ("layer_builds", "layer_artifacts"):
            for _col, _def in [
                ("base_image_id", "VARCHAR(128) DEFAULT NULL"),
                ("base_image_name", "VARCHAR(255) DEFAULT NULL"),
                ("base_image_checksum", "VARCHAR(128) DEFAULT NULL"),
                ("base_image_os_hash_algo", "VARCHAR(32) DEFAULT NULL"),
                ("base_image_os_hash_value", "VARCHAR(128) DEFAULT NULL"),
                ("base_image_min_disk", "INT DEFAULT NULL"),
                ("base_image_visibility", "VARCHAR(32) DEFAULT NULL"),
                ("base_image_owner", "VARCHAR(128) DEFAULT NULL"),
                ("source_metadata", "JSON DEFAULT NULL"),
            ]:
                try:
                    await conn.exec_driver_sql(f"ALTER TABLE {_table} ADD COLUMN {_col} {_def}")
                except Exception:
                    pass  # 이미 존재하면 무시

        # Public squashfs publication and caller-owned consume tracking (022, 없는 경우에만)
        for _col_sql in [
            "ALTER TABLE layer_consumes ADD COLUMN project_id VARCHAR(64) DEFAULT NULL",
            "ALTER TABLE layer_consumes ADD COLUMN artifact_ids JSON DEFAULT NULL",
            "ALTER TABLE layer_consumes ADD INDEX ix_layer_consumes_project_id (project_id)",
            "ALTER TABLE layer_artifacts ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE layer_artifacts ADD INDEX ix_layer_artifacts_is_published (is_published)",
            "ALTER TABLE layer_profiles ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE layer_profiles ADD INDEX ix_layer_profiles_is_published (is_published)",
        ]:
            try:
                await conn.exec_driver_sql(_col_sql)
            except Exception:
                pass  # 이미 존재하면 무시
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS layer_import_jobs ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "source_type VARCHAR(32) NOT NULL DEFAULT 'github_dockerfile',"
                "status VARCHAR(32) NOT NULL DEFAULT 'queued',"
                "progress_step VARCHAR(64) DEFAULT NULL,"
                "progress_pct INT NOT NULL DEFAULT 0,"
                "error_message TEXT DEFAULT NULL,"
                "github_url VARCHAR(512) NOT NULL,"
                "repo_owner VARCHAR(64) NOT NULL,"
                "repo_name VARCHAR(128) NOT NULL,"
                "commit_sha CHAR(40) NOT NULL,"
                "dockerfile_path VARCHAR(255) NOT NULL DEFAULT 'Dockerfile',"
                "layer_prefix VARCHAR(64) NOT NULL,"
                "profile_name VARCHAR(64) NOT NULL,"
                "ubuntu_base VARCHAR(255) NOT NULL,"
                "base_image_id VARCHAR(128) NOT NULL,"
                "base_image_name VARCHAR(255) DEFAULT NULL,"
                "base_image_checksum VARCHAR(128) DEFAULT NULL,"
                "base_image_os_hash_algo VARCHAR(32) DEFAULT NULL,"
                "base_image_os_hash_value VARCHAR(128) DEFAULT NULL,"
                "base_image_min_disk INT DEFAULT NULL,"
                "planned_layers JSON DEFAULT NULL,"
                "artifact_ids JSON DEFAULT NULL,"
                "build_ids JSON DEFAULT NULL,"
                "created_at DATETIME(6) NOT NULL,"
                "updated_at DATETIME(6) NOT NULL,"
                "completed_at DATETIME(6) DEFAULT NULL,"
                "KEY ix_layer_import_jobs_status (status),"
                "KEY ix_layer_import_jobs_created_at (created_at)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass

        for _col, _def in [
            ("source_type", "VARCHAR(32) NOT NULL DEFAULT 'github_dockerfile'"),
            ("status", "VARCHAR(32) NOT NULL DEFAULT 'queued'"),
            ("progress_step", "VARCHAR(64) DEFAULT NULL"),
            ("progress_pct", "INT NOT NULL DEFAULT 0"),
            ("error_message", "TEXT DEFAULT NULL"),
            ("github_url", "VARCHAR(512) NOT NULL"),
            ("repo_owner", "VARCHAR(64) NOT NULL"),
            ("repo_name", "VARCHAR(128) NOT NULL"),
            ("commit_sha", "CHAR(40) NOT NULL"),
            ("dockerfile_path", "VARCHAR(255) NOT NULL DEFAULT 'Dockerfile'"),
            ("layer_prefix", "VARCHAR(64) NOT NULL"),
            ("profile_name", "VARCHAR(64) NOT NULL"),
            ("ubuntu_base", "VARCHAR(255) NOT NULL"),
            ("base_image_id", "VARCHAR(128) NOT NULL"),
            ("base_image_name", "VARCHAR(255) DEFAULT NULL"),
            ("base_image_checksum", "VARCHAR(128) DEFAULT NULL"),
            ("base_image_os_hash_algo", "VARCHAR(32) DEFAULT NULL"),
            ("base_image_os_hash_value", "VARCHAR(128) DEFAULT NULL"),
            ("base_image_min_disk", "INT DEFAULT NULL"),
            ("planned_layers", "JSON DEFAULT NULL"),
            ("artifact_ids", "JSON DEFAULT NULL"),
            ("build_ids", "JSON DEFAULT NULL"),
            ("completed_at", "DATETIME(6) DEFAULT NULL"),
        ]:
            try:
                await conn.exec_driver_sql(f"ALTER TABLE layer_import_jobs ADD COLUMN {_col} {_def}")
            except Exception:
                pass
        for _idx_sql in [
            "ALTER TABLE layer_import_jobs ADD INDEX ix_layer_import_jobs_status (status)",
            "ALTER TABLE layer_import_jobs ADD INDEX ix_layer_import_jobs_created_at (created_at)",
        ]:
            try:
                await conn.exec_driver_sql(_idx_sql)
            except Exception:
                pass

        # 셀프서비스 프로젝트 관리자 역할 테이블
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS project_roles ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "project_id VARCHAR(64) NOT NULL,"
                "user_id VARCHAR(64) NOT NULL,"
                "role VARCHAR(32) NOT NULL DEFAULT 'manager',"
                "granted_by VARCHAR(64) NOT NULL,"
                "created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                "UNIQUE KEY uq_project_user_role (project_id, user_id, role),"
                "KEY idx_project_roles_project (project_id),"
                "KEY idx_project_roles_user (user_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass

        # 프로젝트 이메일 초대 테이블
        try:
            await conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS project_invitations ("
                "id INT AUTO_INCREMENT PRIMARY KEY,"
                "project_id VARCHAR(64) NOT NULL,"
                "invited_email VARCHAR(255) NOT NULL,"
                "invited_user_id VARCHAR(64) DEFAULT NULL,"
                "invited_by VARCHAR(64) NOT NULL,"
                "invited_by_name VARCHAR(255) NOT NULL DEFAULT '',"
                "token_hash VARCHAR(64) NOT NULL UNIQUE,"
                "status VARCHAR(16) NOT NULL DEFAULT 'pending',"
                "keystone_role VARCHAR(64) NOT NULL DEFAULT 'member',"
                "expires_at DATETIME(6) NOT NULL,"
                "accepted_at DATETIME(6) DEFAULT NULL,"
                "created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                "updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),"
                "KEY idx_project_invitations_status (project_id, status),"
                "KEY idx_project_invitations_email (invited_email)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        except Exception:
            pass

        # Stampede 오토스케일 컬럼 추가 (014_stampede, 없는 경우에만)
        try:
            await conn.exec_driver_sql(
                "ALTER TABLE k3s_clusters ADD COLUMN stampede_enabled TINYINT(1) NOT NULL DEFAULT 0"
            )
        except Exception:
            pass  # 이미 존재하면 무시

        for _col_sql in [
            "ALTER TABLE k3s_nodegroups ADD COLUMN stampede_enabled TINYINT(1) NOT NULL DEFAULT 0",
            "ALTER TABLE k3s_nodegroups ADD COLUMN min_size INT NOT NULL DEFAULT 0",
            "ALTER TABLE k3s_nodegroups ADD COLUMN max_size INT NOT NULL DEFAULT 5",
            "ALTER TABLE k3s_nodegroups ADD COLUMN stampede_state JSON DEFAULT NULL",
        ]:
            try:
                await conn.exec_driver_sql(_col_sql)
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
