#!/usr/bin/env python3
"""config.toml → K8s configmap.yaml + secret.yaml + grafana-deployment.yaml 변환기.

현재 config.toml (및 config.*.toml 오버라이드)을 읽어
deploy/k8s/{secret.yaml, configmap.yaml, grafana-deployment.yaml}을 자동 생성합니다.

grafana-deployment.yaml 은 anonymous 인증으로 동작하는 Grafana Deployment 매니페스트로,
iframe 임베드를 위해 GF_SECURITY_ALLOW_EMBEDDING 이 활성화되어 있습니다.
Afterglow 앱 인증이 실질적인 접근 게이트 역할을 합니다.

사용법:
    python3 generate_k8s.py
    python3 generate_k8s.py --config /path/to/config.toml
    python3 generate_k8s.py --output-dir /path/to/deploy/k8s

Python 3.12+ 표준 라이브러리만 사용합니다.
"""

import argparse
import os
import sys
import tempfile
import tomllib
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
REDIS_K8S = "redis://redis.afterglow.svc.cluster.local:6379/0"

# ANSI 색상 (Windows에서는 비활성화)
_USE_COLOR = os.name != "nt" or os.environ.get("FORCE_COLOR")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def green(t: str) -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str) -> str: return _c("31", t)
def dim(t: str) -> str: return _c("2", t)


# ─────────────────────────────────────────────────────────────────────────────
# 설정 로드
# ─────────────────────────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> None:
    """dict를 재귀적으로 병합 (list는 덮어쓰기, dict는 재귀 병합)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def load_config(config_path: Path) -> dict:
    """config.toml + config.*.toml 오버라이드 파일을 로드하고 딥 머지."""
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    # 알파벳순으로 오버라이드 파일 적용 (뒤 파일이 앞을 이김)
    for override_path in sorted(config_path.parent.glob("config.*.toml")):
        # config.toml.example 등은 건너뜀 (확장자가 .toml인 것만)
        if not override_path.name.endswith(".toml"):
            continue
        # 자기 자신은 건너뜀
        if override_path.resolve() == config_path.resolve():
            continue
        with open(override_path, "rb") as f:
            _deep_merge(cfg, tomllib.load(f))
        print(f"  {dim(f'오버라이드 로드: {override_path.name}')}")
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# YAML 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

def _yaml_str(v: str) -> str:
    """YAML 스칼라 값을 안전하게 따옴표로 감싸서 렌더링."""
    if any(c in v for c in ('"', "'", ":", "#", "\n", "\\", "{", "}")):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{v}"'


def _yaml_block_scalar(v: str) -> str:
    """멀티라인 YAML block scalar (|) 렌더링 — SSH 개인키 등에 사용.

    단일 라인이면 _yaml_str로 위임. 빈 값이면 빈 문자열 반환.
    """
    if not v:
        return '""'
    if "\n" not in v:
        return _yaml_str(v)
    lines = v.splitlines()
    body = "\n".join("    " + line for line in lines)
    return "|\n" + body


# ─────────────────────────────────────────────────────────────────────────────
# TOML 헬퍼 (렌더링용)
# ─────────────────────────────────────────────────────────────────────────────

def _toml_str(v: str) -> str:
    """TOML 문자열 값 이스케이프."""
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_bool(v: bool) -> str:
    return "true" if v else "false"


def _toml_list_str(items: list[str]) -> str:
    return "[" + ", ".join(_toml_str(i) for i in items) + "]"


def _toml_val(v) -> str:
    """Python 값을 TOML 값 문자열로 변환."""
    if isinstance(v, bool):
        return _toml_bool(v)
    if isinstance(v, str):
        return _toml_str(v)
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        if all(isinstance(i, str) for i in v):
            return _toml_list_str(v)
        return str(v)
    return _toml_str(str(v))


# ─────────────────────────────────────────────────────────────────────────────
# secret.yaml 렌더링
# ─────────────────────────────────────────────────────────────────────────────

def render_secret(cfg: dict) -> str:
    """secret.yaml 생성: 비밀 값만 추출."""
    os_cfg = cfg.get("openstack", {})
    app = cfg.get("app", {})
    oidc = cfg.get("gitlab_oidc", {})
    k3s = cfg.get("k3s", {})
    db = cfg.get("database", {})
    mon = cfg.get("monitoring", {})
    notion = cfg.get("notion", {})
    builder = cfg.get("builder", {})

    lines = [
        "apiVersion: v1",
        "kind: Secret",
        "metadata:",
        "  name: afterglow-secrets",
        "  namespace: afterglow",
        "type: Opaque",
        "stringData:",
        "  # OpenStack 관리자 계정 비밀번호",
        f'  OS_PASSWORD: {_yaml_str(os_cfg.get("password", ""))}',
        "",
        "  # FastAPI 세션/JWT 서명용 시크릿 키",
        "  # 생성: python3 -c \"import secrets; print(secrets.token_hex(32))\"",
        f'  SECRET_KEY: {_yaml_str(app.get("secret_key", ""))}',
    ]

    client_secret = oidc.get("client_secret", "")
    if client_secret:
        lines.extend([
            "",
            "  # GitLab OIDC Client Secret",
            f'  GITLAB_OIDC_CLIENT_SECRET: {_yaml_str(client_secret)}',
        ])

    enc_key = k3s.get("kubeconfig_encryption_key", "")
    if enc_key:
        lines.extend([
            "",
            "  # k3s kubeconfig 암호화 키",
            "  # 생성: python3 -c \"import secrets; print(secrets.token_hex(32))\"",
            f'  K3S_KUBECONFIG_ENCRYPTION_KEY: {_yaml_str(enc_key)}',
        ])

    db_url = db.get("url", "")
    if db_url:
        lines.extend([
            "",
            "  # 애플리케이션 데이터베이스 연결 URL",
            f'  DATABASE_URL: {_yaml_str(db_url)}',
        ])

    prometheus_password = mon.get("prometheus_password", "")
    if prometheus_password:
        lines.extend([
            "",
            "  # Prometheus basic auth 비밀번호",
            f'  PROMETHEUS_PASSWORD: {_yaml_str(prometheus_password)}',
        ])

    sd_token = mon.get("sd_token", "")
    if sd_token:
        lines.extend([
            "",
            "  # Prometheus SD 엔드포인트 인증 토큰",
            f'  MONITORING_SD_TOKEN: {_yaml_str(sd_token)}',
        ])

    notion_enc_key = notion.get("config_encryption_key", "")
    if notion_enc_key:
        lines.extend([
            "",
            "  # Notion 설정 암호화 키",
            f'  NOTION_CONFIG_ENCRYPTION_KEY: {_yaml_str(notion_enc_key)}',
        ])

    smtp = cfg.get("smtp", {})
    smtp_password = smtp.get("password", "")
    if smtp_password:
        lines.extend([
            "",
            "  # SMTP 이메일 서버 인증 비밀번호",
            f'  SMTP_PASSWORD: {_yaml_str(smtp_password)}',
        ])

    ssh_private_key = builder.get("ssh_private_key", "")
    if ssh_private_key:
        lines.extend([
            "",
            "  # Builder VM SSH 개인키 — /etc/afterglow/ssh/builder.key 로 볼륨 마운트됨",
            f'  BUILDER_SSH_PRIVATE_KEY: {_yaml_block_scalar(ssh_private_key)}',
        ])

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# config.toml 인라인 렌더링 (비밀 제외)
# ─────────────────────────────────────────────────────────────────────────────

def _render_toml_for_k8s(cfg: dict) -> str:
    """config.toml 전체를 렌더링하되 비밀 값은 주석으로 대체."""
    os_cfg = cfg.get("openstack", {})
    app = cfg.get("app", {})
    cache = cfg.get("cache", {})
    sess = cfg.get("session", {})
    nova = cfg.get("nova", {})
    gpu = cfg.get("gpu", {})
    svc = cfg.get("services", {})
    k3s = cfg.get("k3s", {})
    builder = cfg.get("builder", {})
    union = cfg.get("union", {})
    db = cfg.get("database", {})
    cors = cfg.get("cors", {})
    oidc = cfg.get("gitlab_oidc", {})
    logging_cfg = cfg.get("logging", {})
    mon = cfg.get("monitoring", {})
    notion = cfg.get("notion", {})
    smtp = cfg.get("smtp", {})

    lines = [
        "# Afterglow 통합 설정 파일",
        "# 비밀 값은 secret.yaml의 환경변수로 주입됩니다.",
        "",
    ]

    # [openstack]
    lines.append("[openstack]")
    lines.append(f'auth_url = {_toml_str(os_cfg.get("auth_url", ""))}')
    lines.append(f'project_name = {_toml_str(os_cfg.get("project_name", "admin"))}')
    lines.append(f'project_domain_name = {_toml_str(os_cfg.get("project_domain_name", "Default"))}')
    lines.append(f'user_domain_name = {_toml_str(os_cfg.get("user_domain_name", "Default"))}')
    lines.append(f'region_name = {_toml_str(os_cfg.get("region_name", "RegionOne"))}')
    lines.append(f'username = {_toml_str(os_cfg.get("username", "admin"))}')
    lines.append("# password는 secret.yaml의 OS_PASSWORD 환경변수로 주입됩니다")
    if os_cfg.get("insecure"):
        lines.append("insecure = true")
    if os_cfg.get("cacert"):
        lines.append(f'cacert = {_toml_str(os_cfg["cacert"])}')
    lines.append("")
    lines.append("# Manila 설정")
    lines.append(f'manila_endpoint = {_toml_str(os_cfg.get("manila_endpoint", ""))}')
    lines.append(f'manila_share_network_id = {_toml_str(os_cfg.get("manila_share_network_id", ""))}')
    lines.append(f'manila_share_type = {_toml_str(os_cfg.get("manila_share_type", "cephfs"))}')
    lines.append(f'manila_nfs_share_type = {_toml_str(os_cfg.get("manila_nfs_share_type", "nfstype"))}')
    lines.append("")
    lines.append("# Ceph 모니터 (cloud-init CephFS 마운트용, 콤마 구분)")
    lines.append(f'ceph_monitors = {_toml_str(os_cfg.get("ceph_monitors", ""))}')
    lines.append("")
    lines.append("# Union Mount 전용 service 프로젝트 UUID (Manila share + Builder VM)")
    lines.append(f'service_project_id = {_toml_str(os_cfg.get("service_project_id", ""))}')
    lines.append("")
    lines.append("# Swift 설정")
    lines.append(f'swift_endpoint = {_toml_str(os_cfg.get("swift_endpoint", ""))}')
    lines.append(f'swift_upload_timeout = {os_cfg.get("swift_upload_timeout", 600)}')
    lines.append(f'trash_retention_days = {os_cfg.get("trash_retention_days", 30)}')
    lines.append("")
    lines.append("# Manila NFS 설정")
    lines.append(f'manila_nfs_root_squash = {_toml_bool(os_cfg.get("manila_nfs_root_squash", True))}')
    lines.append(f'manila_nfs_sec_flavor = {_toml_str(os_cfg.get("manila_nfs_sec_flavor", "sys"))}')
    lines.append(f'manila_cephx_key_timeout_seconds = {os_cfg.get("manila_cephx_key_timeout_seconds", 300)}')
    lines.append(f'interface = {_toml_str(os_cfg.get("interface", "internal"))}')
    lines.append("")

    # [app]
    lines.append("[app]")
    lines.append(f'backend_port = {app.get("backend_port", 8000)}')
    lines.append(f'frontend_port = {app.get("frontend_port", 3000)}')
    lines.append("# secret_key는 secret.yaml의 SECRET_KEY 환경변수로 주입됩니다")
    lines.append("")
    lines.append("# 사이트 표시 이름 및 설명")
    lines.append(f'site_name = {_toml_str(app.get("site_name", "afterglow"))}')
    lines.append(f'site_description = {_toml_str(app.get("site_description", ""))}')
    lines.append("")
    lines.append("# 로고 및 파비콘 경로 (frontend/static/ 기준)")
    lines.append(f'logo_path = {_toml_str(app.get("logo_path", "/logo.png"))}')
    lines.append(f'favicon_path = {_toml_str(app.get("favicon_path", "/favicon.ico"))}')
    lines.append("")
    lines.append("# 프론트엔드 대시보드 자동 새로고침 간격 (밀리초)")
    lines.append(f'refresh_interval_ms = {app.get("refresh_interval_ms", 5000)}')
    lines.append("")
    lines.append("# 초대 이메일 링크 생성에 사용하는 프론트엔드 베이스 URL")
    lines.append(f'frontend_base_url = {_toml_str(app.get("frontend_base_url", ""))}')
    lines.append("")

    # [logging] (선택)
    if logging_cfg:
        lines.append("[logging]")
        for k, v in logging_cfg.items():
            lines.append(f'{k} = {_toml_val(v)}')
        lines.append("")

    # [cache]
    lines.append("[cache]")
    lines.append(f'redis_url = {_toml_str(REDIS_K8S)}')
    lines.append("# TTL 티어 (초)")
    lines.append(f'ttl_fast = {cache.get("ttl_fast", 15)}      # 인스턴스, 볼륨, 플로팅IP')
    lines.append(f'ttl_normal = {cache.get("ttl_normal", 30)}    # 네트워크, 라우터, 대시보드')
    lines.append(f'ttl_slow = {cache.get("ttl_slow", 60)}      # 키페어, 보안그룹')
    lines.append(f'ttl_static = {cache.get("ttl_static", 300)}   # 이미지, 플레이버, 토큰 검증')
    lines.append(f'default_ttl_seconds = {cache.get("default_ttl_seconds", 30)}')
    lines.append(f'backend = {_toml_str(cache.get("backend", "redis"))}')
    lines.append(f'dynamic_threshold_low = {cache.get("dynamic_threshold_low", 5)}')
    lines.append(f'dynamic_threshold_high = {cache.get("dynamic_threshold_high", 20)}')
    lines.append(f'ttl_identity_stable = {cache.get("ttl_identity_stable", 86400)}')
    lines.append(f'ttl_catalog_slow = {cache.get("ttl_catalog_slow", 900)}')
    lines.append(f'ttl_project_meta = {cache.get("ttl_project_meta", 300)}')
    lines.append(f'ttl_operational_live = {cache.get("ttl_operational_live", 30)}')
    lines.append(f'ttl_admin_overview = {cache.get("ttl_admin_overview", 60)}')
    lines.append(f'ttl_auth_token = {cache.get("ttl_auth_token", 60)}')
    lines.append("")

    # [session]
    lines.append("[session]")
    lines.append(f'timeout_seconds = {sess.get("timeout_seconds", 3600)}')
    lines.append(f'warning_before_seconds = {sess.get("warning_before_seconds", 300)}')
    lines.append(f'absolute_timeout = {sess.get("absolute_timeout", 14400)}')
    lines.append(f'jwt_access_ttl = {sess.get("jwt_access_ttl", 900)}')
    lines.append(f'jwt_refresh_ttl = {sess.get("jwt_refresh_ttl", 604800)}')
    lines.append("")

    # [nova]
    lines.append("[nova]")
    lines.append(f'default_network_id = {_toml_str(nova.get("default_network_id", ""))}')
    lines.append(f'default_availability_zone = {_toml_str(nova.get("default_availability_zone", "nova"))}')
    lines.append(f'boot_volume_size_gb = {nova.get("boot_volume_size_gb", 20)}')
    lines.append(f'upper_volume_size_gb = {nova.get("upper_volume_size_gb", 50)}')
    lines.append(f'default_network_enabled = {_toml_bool(nova.get("default_network_enabled", True))}')
    lines.append(f'default_network_cidr = {_toml_str(nova.get("default_network_cidr", "192.168.0.0/24"))}')
    lines.append(f'default_network_external_id = {_toml_str(nova.get("default_network_external_id", ""))}')
    lines.append("")

    # [builder] (선택)
    if builder:
        lines.append("[builder]")
        if "image_id" in builder:
            lines.append(f'image_id = {_toml_str(builder["image_id"])}')
        if "flavor_id" in builder:
            lines.append(f'flavor_id = {_toml_str(builder["flavor_id"])}')
        if "network_id" in builder:
            lines.append(f'network_id = {_toml_str(builder["network_id"])}')
        if "persistent_server_id" in builder:
            lines.append(f'persistent_server_id = {_toml_str(builder["persistent_server_id"])}')
        if "ssh_user" in builder:
            lines.append(f'ssh_user = {_toml_str(builder["ssh_user"])}')
        if "ssh_key_path" in builder:
            lines.append(f'ssh_key_path = {_toml_str(builder["ssh_key_path"])}')
        if "ssh_host" in builder:
            lines.append(f'ssh_host = {_toml_str(builder["ssh_host"])}')
        if "floating_network_id" in builder:
            lines.append(f'floating_network_id = {_toml_str(builder["floating_network_id"])}')
        if "build_timeout" in builder:
            lines.append(f'build_timeout = {builder["build_timeout"]}')
        lines.append("")

    # [union]
    lines.append("[union]")
    lines.append(f'layer_store_rw_share_id = {_toml_str(union.get("layer_store_rw_share_id", ""))}')
    lines.append(f'layer_store_ro_share_id = {_toml_str(union.get("layer_store_ro_share_id", ""))}')
    lines.append(f'manifest_store_share_id = {_toml_str(union.get("manifest_store_share_id", ""))}')
    lines.append("")

    # [gpu] (디바이스 맵은 config.gpu.toml로 분리)
    lines.append("[gpu]")
    if "available_visible" in gpu:
        lines.append(f'available_visible = {_toml_bool(gpu["available_visible"])}')
    lines.append("# GPU 디바이스 맵은 config.gpu.toml에서 관리됩니다")
    lines.append("")

    # [services]
    lines.append("[services]")
    for svc_name in ("magnum", "manila", "zun", "k3s", "swift", "trove", "barbican"):
        if svc_name in svc:
            lines.append(f'{svc_name} = {_toml_bool(svc[svc_name])}')
    lines.append("")

    # [k3s]
    lines.append("[k3s]")
    k3s_keys_str = (
        "version", "server_flavor_id", "default_agent_flavor_id", "server_image_id",
        "fcos_image_id",
        "callback_base_url", "occm_image", "occm_floating_network_id", "occm_public_network_name",
        "cinder_csi_image", "cinder_csi_default_az", "manila_csi_image", "manila_csi_nfs_image",
        "manila_csi_share_protocol", "keystone_auth_image", "keystone_auth_policy",
        "octavia_ingress_image",
        "octavia_ingress_subnet_id", "octavia_ingress_floating_network_id",
        "barbican_kms_image", "barbican_kms_kek_id",
        "api_lb_vip_network_id", "api_lb_floating_network_id", "lb_subnet_id",
        "cert_rotation_job_image",
    )
    k3s_keys_int = (
        "boot_volume_size_gb", "cert_rotation_node_timeout_sec",
        "stampede_interval", "stampede_scale_down_window",
        "stampede_scale_up_cooldown", "stampede_scale_down_cooldown",
    )
    k3s_keys_float = ("stampede_scale_down_threshold", "stampede_resource_headroom_factor")
    k3s_keys_bool = (
        "occm_enabled", "cinder_csi_enabled", "manila_csi_enabled",
        "keystone_auth_enabled", "octavia_ingress_enabled", "barbican_kms_enabled",
        "api_lb_enabled", "stampede_enabled",
    )
    k3s_keys_str = k3s_keys_str + ("stampede_project_id",)
    for key in k3s_keys_str:
        if key in k3s:
            lines.append(f'{key} = {_toml_str(k3s[key])}')
    for key in k3s_keys_int:
        if key in k3s:
            lines.append(f'{key} = {k3s[key]}')
    for key in k3s_keys_float:
        if key in k3s:
            lines.append(f'{key} = {float(k3s[key])}')
    for key in k3s_keys_bool:
        if key in k3s:
            lines.append(f'{key} = {_toml_bool(k3s[key])}')
    lines.append("# kubeconfig_encryption_key는 secret.yaml의 K3S_KUBECONFIG_ENCRYPTION_KEY 환경변수로 주입됩니다")
    lines.append("")

    # [database] (url은 비밀, 나머지는 포함)
    if db:
        lines.append("[database]")
        lines.append("# url은 secret.yaml의 DATABASE_URL 환경변수로 주입됩니다")
        if "pool_size" in db:
            lines.append(f'pool_size = {db["pool_size"]}')
        if "max_overflow" in db:
            lines.append(f'max_overflow = {db["max_overflow"]}')
        if "auto_create_tables" in db:
            lines.append(f'auto_create_tables = {_toml_bool(db["auto_create_tables"])}')
        if "connect_timeout" in db:
            lines.append(f'connect_timeout = {db["connect_timeout"]}')
        if "pool_timeout" in db:
            lines.append(f'pool_timeout = {db["pool_timeout"]}')
        if "unhealthy_seconds" in db:
            lines.append(f'unhealthy_seconds = {db["unhealthy_seconds"]}')
        if "db_auto_backup_cron" in db:
            lines.append(f'db_auto_backup_cron = {_toml_str(db["db_auto_backup_cron"])}')
        lines.append("")

    # [cors]
    lines.append("[cors]")
    lines.append(f'origins = {_toml_str(cors.get("origins", "http://localhost:3000"))}')
    lines.append("")

    # [gitlab_oidc]
    lines.append("[gitlab_oidc]")
    lines.append(f'enabled = {_toml_bool(oidc.get("enabled", False))}')
    lines.append(f'gitlab_url = {_toml_str(oidc.get("gitlab_url", "https://gitlab.com"))}')
    lines.append(f'client_id = {_toml_str(oidc.get("client_id", ""))}')
    lines.append("# client_secret은 secret.yaml의 GITLAB_OIDC_CLIENT_SECRET 환경변수로 주입됩니다")
    lines.append(f'idp_id = {_toml_str(oidc.get("idp_id", "gitlab"))}')
    lines.append(f'protocol_id = {_toml_str(oidc.get("protocol_id", "openid"))}')
    lines.append(f'redirect_uri = {_toml_str(oidc.get("redirect_uri", ""))}')
    lines.append(f'scopes = {_toml_str(oidc.get("scopes", "openid email profile read_user"))}')
    lines.append("")

    # [smtp]
    if smtp.get("host") or smtp.get("enabled"):
        lines.append("[smtp]")
        lines.append(f'enabled = {_toml_bool(smtp.get("enabled", False))}')
        lines.append(f'host = {_toml_str(smtp.get("host", ""))}')
        lines.append(f'port = {smtp.get("port", 587)}')
        lines.append(f'username = {_toml_str(smtp.get("username", ""))}')
        lines.append("# password는 secret.yaml의 SMTP_PASSWORD 환경변수로 주입됩니다")
        lines.append(f'from_address = {_toml_str(smtp.get("from_address", "noreply@afterglow.example.com"))}')
        lines.append(f'from_name = {_toml_str(smtp.get("from_name", "Afterglow"))}')
        lines.append(f'use_tls = {_toml_bool(smtp.get("use_tls", True))}')
        lines.append(f'timeout_seconds = {smtp.get("timeout_seconds", 10)}')
        smtp_inv = smtp.get("invitation", {})
        lines.append("")
        lines.append("[smtp.invitation]")
        lines.append(f'token_expiry_days = {smtp_inv.get("token_expiry_days", 7)}')
        lines.append("")

    # [monitoring]
    lines.append("[monitoring]")
    lines.append(f'prometheus_base_url = {_toml_str(mon.get("prometheus_base_url", "http://prometheus:9090"))}')
    lines.append(f'prometheus_username = {_toml_str(mon.get("prometheus_username", ""))}')
    lines.append("# prometheus_password는 secret.yaml의 PROMETHEUS_PASSWORD 환경변수로 주입됩니다")
    lines.append(f'scrape_cidr = {_toml_str(mon.get("scrape_cidr", ""))}')
    lines.append(f'auto_sg_enabled = {_toml_bool(mon.get("auto_sg_enabled", True))}')
    lines.append(f'node_exporter_sg_name = {_toml_str(mon.get("node_exporter_sg_name", "node_exporter"))}')
    lines.append(f'dcgm_exporter_sg_name = {_toml_str(mon.get("dcgm_exporter_sg_name", "dcgm_exporter"))}')
    lines.append(f'node_exporter_port = {mon.get("node_exporter_port", 9100)}')
    lines.append(f'dcgm_exporter_port = {mon.get("dcgm_exporter_port", 9400)}')
    lines.append(f'libvirt_exporter_port = {mon.get("libvirt_exporter_port", 9177)}')
    lines.append(f'gpu_flavor_prefix = {_toml_str(mon.get("gpu_flavor_prefix", "gpu."))}')
    lines.append(f'grafana_base_url = {_toml_str(mon.get("grafana_base_url", ""))}')
    lines.append("# sd_token은 secret.yaml의 MONITORING_SD_TOKEN 환경변수로 주입됩니다")
    dashboards = mon.get("dashboards", {})
    lines.append("")
    lines.append("[monitoring.dashboards]")
    lines.append(f'node_uid = {_toml_str(dashboards.get("node_uid", "afterglow-node"))}')
    lines.append(f'rabbitmq_uid = {_toml_str(dashboards.get("rabbitmq_uid", "afterglow-rabbitmq"))}')
    lines.append(f'mysqld_uid = {_toml_str(dashboards.get("mysqld_uid", "afterglow-mysqld"))}')
    lines.append(f'memcached_uid = {_toml_str(dashboards.get("memcached_uid", "afterglow-memcached"))}')
    lines.append(f'etcd_uid = {_toml_str(dashboards.get("etcd_uid", "afterglow-etcd"))}')
    lines.append(f'haproxy_uid = {_toml_str(dashboards.get("haproxy_uid", "afterglow-haproxy"))}')
    lines.append(f'libvirt_uid = {_toml_str(dashboards.get("libvirt_uid", "afterglow-libvirt"))}')
    lines.append(f'openstack_uid = {_toml_str(dashboards.get("openstack_uid", "afterglow-openstack"))}')
    lines.append(f'ceph_uid = {_toml_str(dashboards.get("ceph_uid", "afterglow-ceph"))}')
    lines.append(f'instance_cpu_uid = {_toml_str(dashboards.get("instance_cpu_uid", "afterglow-instance-cpu"))}')
    lines.append(f'instance_gpu_uid = {_toml_str(dashboards.get("instance_gpu_uid", "afterglow-instance-gpu"))}')
    lines.append("")

    # [notion]
    if notion.get("config_encryption_key"):
        lines.append("[notion]")
        lines.append("# config_encryption_key는 secret.yaml의 NOTION_CONFIG_ENCRYPTION_KEY 환경변수로 주입됩니다")
        lines.append("")

    # [security]
    security = cfg.get("security", {})
    lines.append("[security]")
    lines.append(f'admin_legacy_project_policy = {_toml_bool(security.get("admin_legacy_project_policy", True))}')
    lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# config.gpu.toml 렌더링
# ─────────────────────────────────────────────────────────────────────────────

def _render_gpu_toml(cfg: dict) -> str:
    """config.gpu.toml 렌더링: GPU 디바이스 맵."""
    gpu = cfg.get("gpu", {})
    devices = gpu.get("devices", [])
    if not devices:
        return ""

    lines = [
        "# Afterglow GPU 디바이스 맵",
        "# config.toml과 함께 로드되어 딥 머지됩니다.",
        "",
    ]
    for dev in devices:
        lines.append("[[gpu.devices]]")
        lines.append(f'vendor_id = {_toml_str(dev.get("vendor_id", ""))}')
        lines.append(f'device_id = {_toml_str(dev.get("device_id", ""))}')
        lines.append(f'name = {_toml_str(dev.get("name", ""))}')
        lines.append(f'is_audio = {_toml_bool(dev.get("is_audio", False))}')
        aliases = dev.get("aliases", [])
        if aliases:
            lines.append(f'aliases = {_toml_list_str(aliases)}')
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# configmap.yaml 렌더링
# ─────────────────────────────────────────────────────────────────────────────

def render_configmap(cfg: dict) -> str:
    """configmap.yaml 생성: Redis URL, Origin, S3 base, config.toml + config.gpu.toml 인라인."""
    cors = cfg.get("cors", {})
    ost = cfg.get("openstack", {})

    # APP_ORIGIN: cors.origins 의 첫 번째 항목 (프로덕션 도메인)
    origins_raw = cors.get("origins", "http://localhost:3000")
    app_origin = origins_raw.split(",")[0].strip()

    # APP_S3_BASE: openstack.s3_endpoint (미설정 시 기본값)
    app_s3_base = ost.get("s3_endpoint", "https://s3.dmslab.re.kr")

    # APP_GRAFANA_BASE: monitoring.grafana_base_url (CSP frame-src 및 frontend 임베드용)
    app_grafana_base = cfg.get("monitoring", {}).get("grafana_base_url", "")

    # config.toml 인라인 (4칸 들여쓰기)
    toml_content = _render_toml_for_k8s(cfg)
    indented_toml = "\n".join("    " + line for line in toml_content.splitlines())

    lines = [
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        "  name: afterglow-config",
        "  namespace: afterglow",
        "data:",
        f'  APP_REDIS_URL: "{REDIS_K8S}"',
        f'  APP_ORIGIN: "{app_origin}"',
        f'  APP_S3_BASE: "{app_s3_base}"',
        f'  APP_GRAFANA_BASE: "{app_grafana_base}"',
        "  config.toml: |",
        indented_toml,
    ]

    # config.gpu.toml (GPU 디바이스 맵이 있는 경우에만)
    gpu_content = _render_gpu_toml(cfg)
    if gpu_content:
        indented_gpu = "\n".join("    " + line for line in gpu_content.splitlines())
        lines.extend([
            "  config.gpu.toml: |",
            indented_gpu,
        ])

    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# grafana-deployment.yaml 렌더링
# ─────────────────────────────────────────────────────────────────────────────

def render_grafana_deployment(cfg: dict) -> str:
    """grafana-deployment.yaml 생성.

    iframe 임베드(GF_SECURITY_ALLOW_EMBEDDING)와 익명 접근(auth.anonymous)을 설정한다.
    provisioning ConfigMap (datasource + dashboards)을 volumeMounts로 마운트한다.
    """
    mon = cfg.get("monitoring", {})
    admin_password = mon.get("grafana_admin_password", "admin")
    lines = [
        "apiVersion: apps/v1",
        "kind: Deployment",
        "metadata:",
        "  name: grafana",
        "  namespace: afterglow",
        "  labels:",
        "    app: grafana",
        "spec:",
        "  replicas: 1",
        "  selector:",
        "    matchLabels:",
        "      app: grafana",
        "  template:",
        "    metadata:",
        "      labels:",
        "        app: grafana",
        "    spec:",
        "      containers:",
        "        - name: grafana",
        "          image: grafana/grafana:11.0.0",
        "          ports:",
        "            - containerPort: 3000",
        "          env:",
        "            - name: GF_SECURITY_ADMIN_PASSWORD",
        f'              value: "{admin_password}"',
        "            - name: GF_USERS_ALLOW_SIGN_UP",
        '              value: "false"',
        "            - name: GF_SECURITY_ALLOW_EMBEDDING",
        '              value: "true"',
        "            - name: GF_AUTH_ANONYMOUS_ENABLED",
        '              value: "true"',
        "            - name: GF_AUTH_ANONYMOUS_ORG_ROLE",
        '              value: "Viewer"',
        "          volumeMounts:",
        "            - name: grafana-datasource",
        "              mountPath: /etc/grafana/provisioning/datasources",
        "            - name: grafana-dashboards-provider",
        "              mountPath: /etc/grafana/provisioning/dashboards",
        "            - name: grafana-dashboards",
        "              mountPath: /var/lib/grafana/dashboards",
        "          resources:",
        "            requests:",
        '              memory: "128Mi"',
        '              cpu: "100m"',
        "            limits:",
        '              memory: "256Mi"',
        '              cpu: "200m"',
        "      volumes:",
        "        - name: grafana-datasource",
        "          configMap:",
        "            name: grafana-datasource",
        "        - name: grafana-dashboards-provider",
        "          configMap:",
        "            name: grafana-dashboards-provider",
        "        - name: grafana-dashboards",
        "          configMap:",
        "            name: grafana-dashboards",
        "",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 파일 쓰기
# ─────────────────────────────────────────────────────────────────────────────

def write_atomic(path: Path, content: str) -> None:
    """임시 파일로 쓴 뒤 원자적으로 교체 (부분 쓰기 방지)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".gen_k8s_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ─────────────────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="config.toml → K8s configmap.yaml + secret.yaml 변환기"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=SCRIPT_DIR / "config.toml",
        help="config.toml 경로 (기본값: ./config.toml)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "deploy" / "k8s",
        help="출력 디렉토리 (기본값: ./deploy/k8s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 쓰지 않고 내용만 출력",
    )
    args = parser.parse_args()

    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()

    if not config_path.exists():
        print(f"{red('오류')}: config.toml을 찾을 수 없습니다: {config_path}", file=sys.stderr)
        sys.exit(1)

    print(f"  설정 로드: {dim(str(config_path))}")
    cfg = load_config(config_path)
    print(f"  {green('✓')} 설정 로드 완료")
    print()

    # 렌더링
    secret_content = render_secret(cfg)
    configmap_content = render_configmap(cfg)
    grafana_deployment_content = render_grafana_deployment(cfg)

    if args.dry_run:
        print("─" * 60)
        print("# secret.yaml")
        print("─" * 60)
        print(secret_content)
        print("─" * 60)
        print("# configmap.yaml")
        print("─" * 60)
        print(configmap_content)
        print("─" * 60)
        print("# grafana-deployment.yaml")
        print("─" * 60)
        print(grafana_deployment_content)
        return

    # 파일 쓰기
    secret_path = output_dir / "secret.yaml"
    configmap_path = output_dir / "configmap.yaml"
    grafana_deployment_path = output_dir / "grafana-deployment.yaml"

    write_atomic(secret_path, secret_content)
    print(f"  {green('✓')} {secret_path}")

    write_atomic(configmap_path, configmap_content)
    print(f"  {green('✓')} {configmap_path}")

    write_atomic(grafana_deployment_path, grafana_deployment_content)
    print(f"  {green('✓')} {grafana_deployment_path}")

    print()
    print(f"{green('완료!')} K8s 매니페스트가 생성되었습니다.")
    print()
    print(f"  {yellow('주의')}: secret.yaml에 비밀번호가 평문으로 저장됩니다.")
    print(f"        git에 커밋하지 마세요.")
    print()
    print("  적용 방법:")
    print(f"    kubectl apply -f {secret_path}")
    print(f"    kubectl apply -f {configmap_path}")
    print(f"    kubectl apply -f {grafana_deployment_path}")
    print(f"    kubectl rollout restart deployment -n afterglow")


if __name__ == "__main__":
    main()
