"""Afterglow 설정 모듈.

우선순위: 환경변수 > config.toml (프로젝트 루트) > 기본값
"""

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _config_candidates() -> list[Path]:
    """설정 파일 후보 경로 목록. CWD → 상위 → /app (Docker) → afterglow.toml (K8s ConfigMap)."""
    return [
        Path.cwd() / "config.toml",
        Path.cwd().parent / "config.toml",
        Path("/app/config.toml"),
        Path("/app/afterglow.toml"),  # K8s ConfigMap 마운트 경로
        Path.cwd() / "afterglow.toml",
    ]


def _load_toml() -> dict:
    """프로젝트 루트의 config.toml을 읽어 평탄화된 dict를 반환."""
    candidates = _config_candidates()
    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
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
            flat["os_insecure"] = ost.get("insecure", False)
            flat["os_cacert"] = ost.get("cacert", "")
            flat["os_manila_endpoint"] = ost.get("manila_endpoint", "")
            flat["os_manila_share_network_id"] = ost.get("manila_share_network_id", "")
            flat["os_manila_share_type"] = ost.get("manila_share_type", "cephfstype")
            flat["os_manila_nfs_share_type"] = ost.get("manila_nfs_share_type", "nfstype")
            flat["ceph_monitors"] = ost.get("ceph_monitors", "")

            app = data.get("app", {})
            flat["backend_port"] = app.get("backend_port", 8000)
            flat["frontend_port"] = app.get("frontend_port", 3000)
            flat["secret_key"] = app.get("secret_key", "change-me-in-production")
            flat["refresh_interval_ms"] = app.get("refresh_interval_ms", 5000)
            flat["site_name"] = app.get("site_name", "Afterglow")
            flat["site_description"] = app.get("site_description", "OpenStack VM + OverlayFS 배포 플랫폼")
            flat["logo_path"] = app.get("logo_path", "/logo.png")
            flat["favicon_path"] = app.get("favicon_path", "/favicon.ico")

            cache = data.get("cache", {})
            flat["redis_url"] = cache.get("redis_url", "redis://localhost:6379/0")
            flat["cache_ttl_seconds"] = cache.get("default_ttl_seconds", 30)
            flat["cache_ttl_fast"] = cache.get("ttl_fast", 15)
            flat["cache_ttl_normal"] = cache.get("ttl_normal", cache.get("default_ttl_seconds", 30))
            flat["cache_ttl_slow"] = cache.get("ttl_slow", 60)
            flat["cache_ttl_static"] = cache.get("ttl_static", 300)

            svc = data.get("services", {})
            flat["service_magnum_enabled"] = svc.get("magnum", False)
            flat["service_manila_enabled"] = svc.get("manila", False)
            flat["service_zun_enabled"] = svc.get("zun", False)
            flat["service_k3s_enabled"] = svc.get("k3s", False)

            k3s = data.get("k3s", {})
            flat["k3s_version"] = k3s.get("version", "v1.31.4+k3s1")
            flat["k3s_server_flavor_id"] = k3s.get("server_flavor_id", "")
            flat["k3s_default_agent_flavor_id"] = k3s.get("default_agent_flavor_id", "")
            flat["k3s_server_image_id"] = k3s.get("server_image_id", "")
            flat["k3s_callback_base_url"] = k3s.get("callback_base_url", "")
            flat["k3s_kubeconfig_encryption_key"] = k3s.get("kubeconfig_encryption_key", "")
            flat["k3s_boot_volume_size_gb"] = k3s.get("boot_volume_size_gb", 30)
            flat["k3s_occm_enabled"] = k3s.get("occm_enabled", False)
            flat["k3s_occm_image"] = k3s.get(
                "occm_image", "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0"
            )
            flat["k3s_occm_floating_network_id"] = k3s.get("occm_floating_network_id", "")
            flat["k3s_occm_public_network_name"] = k3s.get("occm_public_network_name", "")

            sess = data.get("session", {})
            flat["session_timeout_seconds"] = sess.get("timeout_seconds", 3600)
            flat["session_warning_before_seconds"] = sess.get("warning_before_seconds", 300)
            flat["session_absolute_timeout"] = sess.get("absolute_timeout", 14400)

            nv = data.get("nova", {})
            flat["default_network_id"] = nv.get("default_network_id", "")
            flat["default_availability_zone"] = nv.get("default_availability_zone", "nova")
            flat["boot_volume_size_gb"] = nv.get("boot_volume_size_gb", 20)
            flat["upper_volume_size_gb"] = nv.get("upper_volume_size_gb", 50)

            builder = data.get("builder", {})
            flat["builder_image_id"] = builder.get("image_id", "")
            flat["builder_flavor_id"] = builder.get("flavor_id", "")
            flat["builder_network_id"] = builder.get("network_id", "")

            gl = data.get("gitlab_oidc", {})
            flat["gitlab_oidc_enabled"] = gl.get("enabled", False)
            flat["gitlab_oidc_gitlab_url"] = gl.get("gitlab_url", "")
            flat["gitlab_oidc_client_id"] = gl.get("client_id", "")
            flat["gitlab_oidc_client_secret"] = gl.get("client_secret", "")
            flat["gitlab_oidc_idp_id"] = gl.get("idp_id", "gitlab")
            flat["gitlab_oidc_protocol_id"] = gl.get("protocol_id", "openid")
            flat["gitlab_oidc_redirect_uri"] = gl.get("redirect_uri", "")
            flat["gitlab_oidc_scopes"] = gl.get("scopes", "openid email profile read_user")

            db = data.get("database", {})
            flat["database_url"] = db.get("url", "")
            flat["database_pool_size"] = db.get("pool_size", 5)
            flat["database_max_overflow"] = db.get("max_overflow", 10)
            flat["database_auto_create_tables"] = db.get("auto_create_tables", True)

            cors = data.get("cors", {})
            flat["cors_origins"] = cors.get("origins", "http://localhost:3000,http://localhost")

            log = data.get("logging", {})
            flat["log_file_path"] = log.get("log_file_path", "/app/logs/afterglow-backend.log")
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
    os_insecure: bool = False
    os_cacert: str = ""

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
    site_name: str = "Afterglow"
    site_description: str = "OpenStack VM + OverlayFS 배포 플랫폼"
    logo_path: str = "/logo.png"
    favicon_path: str = "/favicon.ico"

    # Redis 캐시
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 30
    cache_ttl_fast: int = 15
    cache_ttl_normal: int = 30
    cache_ttl_slow: int = 60
    cache_ttl_static: int = 300

    # 선택적 서비스
    service_magnum_enabled: bool = False
    service_manila_enabled: bool = False
    service_zun_enabled: bool = False
    service_k3s_enabled: bool = False

    # k3s 설정
    k3s_version: str = "v1.31.4+k3s1"
    k3s_server_flavor_id: str = ""
    k3s_default_agent_flavor_id: str = ""
    k3s_server_image_id: str = ""
    k3s_callback_base_url: str = ""
    k3s_kubeconfig_encryption_key: str = ""
    k3s_boot_volume_size_gb: int = 30
    k3s_occm_enabled: bool = False
    k3s_occm_image: str = "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.35.0"
    k3s_occm_floating_network_id: str = ""
    k3s_occm_public_network_name: str = ""
    notion_config_encryption_key: str = ""  # 미설정 시 k3s_kubeconfig_encryption_key 재사용

    # 세션 관리
    session_timeout_seconds: int = 3600
    session_warning_before_seconds: int = 300
    session_absolute_timeout: int = 14400  # 절대 만료: 기본 4시간, 초과 시 연장 불가

    # Nova 기본값
    default_network_id: str = ""
    default_availability_zone: str = "nova"
    boot_volume_size_gb: int = 20
    upper_volume_size_gb: int = 50

    # 라이브러리 빌더 VM 설정
    builder_image_id: str = ""  # 빌더 VM 부팅 이미지 ID (Ubuntu 22.04+)
    builder_flavor_id: str = ""  # 빌더 VM 플레이버 ID
    builder_network_id: str = ""  # 빌더 VM 네트워크 ID (미지정 시 default_network_id 사용)

    # 데이터베이스 (MariaDB/MySQL, 선택적)
    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_auto_create_tables: bool = True

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
    log_file_path: str = "/app/logs/afterglow-backend.log"
    log_level: str = "INFO"
    log_max_bytes: int = 52428800  # 50MB
    log_backup_count: int = 5
    log_rotation_type: str = "size"  # "size" | "time"
    log_rotation_when: str = "midnight"
    log_rotation_interval: int = 1

    @property
    def ssl_verify(self) -> bool | str:
        """OpenStack API SSL 검증 설정. cacert 경로가 있으면 해당 경로, insecure면 False, 아니면 True."""
        if self.os_insecure:
            return False
        if self.os_cacert:
            return self.os_cacert
        return True

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
            if os.environ.get("AFTERGLOW_ALLOW_INSECURE", "").strip() == "1":
                logger.warning(
                    "SECRET_KEY is set to the default insecure value. "
                    "AFTERGLOW_ALLOW_INSECURE=1 is set — this must NOT be used in production."
                )
            else:
                raise ValueError(
                    "SECRET_KEY is set to the default value 'change-me-in-production'. "
                    "Set a strong random value in config.toml [app] secret_key or SECRET_KEY env var. "
                    "To override this check in development, set AFTERGLOW_ALLOW_INSECURE=1."
                )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def load_raw_toml() -> dict:
    """config.toml 원본 dict를 반환 (중첩 구조 보존, 평탄화하지 않음)."""
    candidates = _config_candidates()
    for path in candidates:
        if path.exists():
            with open(path, "rb") as f:
                return tomllib.load(f)
    return {}


@lru_cache
def get_settings() -> Settings:
    # K8s 서비스 디스커버리 환경변수 충돌 방지
    # K8s는 서비스명 기반으로 {SVC}_PORT=tcp://IP:PORT 등을 자동 주입하는데,
    # 이것이 우리 설정 필드(backend_port, frontend_port 등)와 충돌할 수 있음.
    _k8s_collision_keys = ("BACKEND_PORT", "FRONTEND_PORT")
    for key in _k8s_collision_keys:
        val = os.environ.get(key, "")
        if val.startswith("tcp://") or val.startswith("udp://"):
            del os.environ[key]

    # TOML 값으로 환경변수를 채워 Settings가 이를 읽도록 함
    # (환경변수 > .env 이므로, TOML 값을 환경변수로 주입하되 이미 설정된 값은 덮어쓰지 않음)
    toml_data = _load_toml()
    for key, value in toml_data.items():
        env_key = key.upper()
        if env_key not in os.environ:
            os.environ[env_key] = str(value)
    return Settings()
