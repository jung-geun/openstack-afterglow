"""Union 설정 모듈.

우선순위: 환경변수 > config.toml (프로젝트 루트) > 기본값
"""

import tomllib
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import model_validator


def _load_toml() -> dict:
    """프로젝트 루트의 config.toml을 읽어 평탄화된 dict를 반환."""
    # 가능한 위치: CWD, CWD 상위, /app (Docker)
    candidates = [
        Path.cwd() / "config.toml",
        Path.cwd().parent / "config.toml",
        Path("/app/config.toml"),
    ]
    for path in candidates:
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            # 섹션을 평탄화하여 Settings 필드에 매핑
            flat: dict = {}
            ost = data.get("openstack", {})
            flat["os_auth_url"] = ost.get("auth_url", "")
            flat["os_username"] = ost.get("username", "")
            flat["os_password"] = ost.get("password", "")
            flat["os_project_name"] = ost.get("project_name", "admin")
            flat["os_project_domain_name"] = ost.get("project_domain_name", "Default")
            flat["os_user_domain_name"] = ost.get("user_domain_name", "Default")
            flat["os_region_name"] = ost.get("region_name", "RegionOne")
            flat["os_manila_endpoint"] = ost.get("manila_endpoint", "")
            flat["os_manila_share_network_id"] = ost.get("manila_share_network_id", "")
            flat["os_manila_share_type"] = ost.get("manila_share_type", "cephfstype")
            flat["ceph_monitors"] = ost.get("ceph_monitors", "")

            app = data.get("app", {})
            flat["backend_port"] = app.get("backend_port", 8000)
            flat["frontend_port"] = app.get("frontend_port", 3000)
            flat["secret_key"] = app.get("secret_key", "change-me-in-production")
            flat["refresh_interval_ms"] = app.get("refresh_interval_ms", 5000)
            flat["site_name"] = app.get("site_name", "Union")
            flat["site_description"] = app.get("site_description", "OpenStack VM + OverlayFS 배포 플랫폼")
            flat["logo_path"] = app.get("logo_path", "/logo.png")
            flat["favicon_path"] = app.get("favicon_path", "/favicon.ico")

            cache = data.get("cache", {})
            flat["redis_url"] = cache.get("redis_url", "redis://localhost:6379/0")
            flat["cache_ttl_seconds"] = cache.get("default_ttl_seconds", 30)

            sess = data.get("session", {})
            flat["session_timeout_seconds"] = sess.get("timeout_seconds", 3600)
            flat["session_warning_before_seconds"] = sess.get("warning_before_seconds", 300)

            nv = data.get("nova", {})
            flat["default_network_id"] = nv.get("default_network_id", "")
            flat["default_availability_zone"] = nv.get("default_availability_zone", "nova")
            flat["boot_volume_size_gb"] = nv.get("boot_volume_size_gb", 20)
            flat["upper_volume_size_gb"] = nv.get("upper_volume_size_gb", 50)

            gl = data.get("gitlab_oidc", {})
            flat["gitlab_oidc_enabled"] = gl.get("enabled", False)
            flat["gitlab_oidc_gitlab_url"] = gl.get("gitlab_url", "")
            flat["gitlab_oidc_client_id"] = gl.get("client_id", "")
            flat["gitlab_oidc_client_secret"] = gl.get("client_secret", "")
            flat["gitlab_oidc_idp_id"] = gl.get("idp_id", "gitlab")
            flat["gitlab_oidc_protocol_id"] = gl.get("protocol_id", "openid")
            flat["gitlab_oidc_redirect_uri"] = gl.get("redirect_uri", "")
            flat["gitlab_oidc_scopes"] = gl.get("scopes", "openid email profile read_user")

            cors = data.get("cors", {})
            flat["cors_origins"] = cors.get("origins", "http://localhost:3000,http://localhost")

            log = data.get("logging", {})
            flat["log_file_path"] = log.get("log_file_path", "/app/logs/union-backend.log")
            flat["log_level"] = log.get("log_level", "INFO")
            flat["log_max_bytes"] = log.get("max_bytes", 52428800)
            flat["log_backup_count"] = log.get("backup_count", 5)
            flat["log_rotation_type"] = log.get("rotation_type", "size")
            flat["log_rotation_when"] = log.get("rotation_when", "midnight")
            flat["log_rotation_interval"] = log.get("rotation_interval", 1)

            return flat
    return {}


class Settings(BaseSettings):
    # OpenStack 인증
    os_auth_url: str = ""
    os_username: str = ""
    os_password: str = ""
    os_project_name: str = "admin"
    os_project_domain_name: str = "Default"
    os_user_domain_name: str = "Default"
    os_region_name: str = "RegionOne"

    # Manila 설정
    os_manila_endpoint: str = ""
    os_manila_share_network_id: str = ""
    os_manila_share_type: str = "cephfstype"

    # Ceph 모니터 (cloud-init CephFS 마운트용)
    ceph_monitors: str = ""

    # 앱 설정
    backend_port: int = 8000
    frontend_port: int = 3000
    secret_key: str = "change-me-in-production"

    # CORS 허용 origin (쉼표 구분)
    cors_origins: str = "http://localhost:3000,http://localhost"
    refresh_interval_ms: int = 5000
    site_name: str = "Union"
    site_description: str = "OpenStack VM + OverlayFS 배포 플랫폼"
    logo_path: str = "/logo.png"
    favicon_path: str = "/favicon.ico"

    # Redis 캐시
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 30

    # 세션 관리
    session_timeout_seconds: int = 3600
    session_warning_before_seconds: int = 300

    # Nova 기본값
    default_network_id: str = ""
    default_availability_zone: str = "nova"
    boot_volume_size_gb: int = 20
    upper_volume_size_gb: int = 50

    # GitLab OIDC
    gitlab_oidc_enabled: bool = False
    gitlab_oidc_gitlab_url: str = ""
    gitlab_oidc_client_id: str = ""
    gitlab_oidc_client_secret: str = ""
    gitlab_oidc_idp_id: str = "gitlab"
    gitlab_oidc_protocol_id: str = "openid"
    gitlab_oidc_redirect_uri: str = ""
    gitlab_oidc_scopes: str = "openid email profile read_user"

    # 로깅 설정
    log_file_path: str = "/app/logs/union-backend.log"
    log_level: str = "INFO"
    log_max_bytes: int = 52428800    # 50MB
    log_backup_count: int = 5
    log_rotation_type: str = "size"  # "size" | "time"
    log_rotation_when: str = "midnight"
    log_rotation_interval: int = 1

    @property
    def ceph_monitor_list(self) -> list[str]:
        return [m.strip() for m in self.ceph_monitors.split(",") if m.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def warn_insecure_defaults(self) -> "Settings":
        import logging
        import os
        logger = logging.getLogger(__name__)
        if self.secret_key == "change-me-in-production":
            if os.environ.get("UNION_ALLOW_INSECURE", "").strip() == "1":
                logger.warning(
                    "SECRET_KEY is set to the default insecure value. "
                    "UNION_ALLOW_INSECURE=1 is set — this must NOT be used in production."
                )
            else:
                raise ValueError(
                    "SECRET_KEY is set to the default value 'change-me-in-production'. "
                    "Set a strong random value in config.toml [app] secret_key or SECRET_KEY env var. "
                    "To override this check in development, set UNION_ALLOW_INSECURE=1."
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def load_raw_toml() -> dict:
    """config.toml 원본 dict를 반환 (중첩 구조 보존, 평탄화하지 않음)."""
    candidates = [
        Path.cwd() / "config.toml",
        Path.cwd().parent / "config.toml",
        Path("/app/config.toml"),
    ]
    for path in candidates:
        if path.exists():
            with open(path, "rb") as f:
                return tomllib.load(f)
    return {}


@lru_cache
def get_settings() -> Settings:
    # TOML 값으로 환경변수를 채워 Settings가 이를 읽도록 함
    # (환경변수 > .env 이므로, TOML 값을 환경변수로 주입하되 이미 설정된 값은 덮어쓰지 않음)
    toml_data = _load_toml()
    for key, value in toml_data.items():
        env_key = key.upper()
        if env_key not in os.environ:
            os.environ[env_key] = str(value)
    return Settings()
