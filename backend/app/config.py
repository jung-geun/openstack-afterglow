from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenStack 인증
    os_auth_url: str = ""
    os_project_name: str = "admin"
    os_project_domain_name: str = "Default"
    os_user_domain_name: str = "Default"
    os_region_name: str = "RegionOne"

    # Manila 설정
    os_manila_endpoint: str = ""          # 수동 오버라이드 (서비스 카탈로그 대신 사용)
    os_manila_share_network_id: str = ""
    os_manila_share_type: str = "cephfstype"

    # Ceph 모니터 (cloud-init CephFS 마운트용)
    ceph_monitors: str = ""  # comma-separated

    # 앱 설정
    backend_port: int = 8000
    secret_key: str = "change-me-in-production"

    # Nova 기본값
    default_network_id: str = ""
    default_availability_zone: str = "nova"
    boot_volume_size_gb: int = 20
    upper_volume_size_gb: int = 50

    @property
    def ceph_monitor_list(self) -> list[str]:
        return [m.strip() for m in self.ceph_monitors.split(",") if m.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
