"""Afterglow 설정 모듈.

우선순위: 환경변수 > afterglow.conf/config.toml (프로젝트 루트) > 기본값
"""

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


def _config_candidates() -> list[Path]:
    """설정 파일 후보 경로 목록.

    afterglow.conf는 TOML 문법을 유지하는 신규 기본 파일명이고,
    config.toml/afterglow.toml은 기존 배포 호환을 위해 계속 지원한다.
    """
    return [
        Path.cwd() / "afterglow.conf",
        Path.cwd().parent / "afterglow.conf",
        Path.cwd() / "config.toml",
        Path.cwd().parent / "config.toml",
        Path("/app/afterglow.conf"),
        Path("/app/config.toml"),
        Path("/app/afterglow.toml"),  # 레거시 K8s ConfigMap 마운트 경로
        Path.cwd() / "afterglow.toml",
    ]


def _deep_merge(base: dict, override: dict) -> dict:
    """base 위에 override를 재귀적으로 딥 머지한 새 dict를 반환.

    dict 값은 재귀 병합, 그 외(스칼라·리스트)는 override가 덮어쓴다.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _config_override_paths(base_path: Path) -> list[Path]:
    """base_path와 같은 디렉토리에서 설정 오버라이드 파일을 알파벳순으로 반환.

    예:
    - base_path=/app/afterglow.conf → afterglow.*.conf, afterglow.*.toml, config.*.toml
    - base_path=/app/config.toml → config.*.toml

    base 자기자신과 크기 0 파일은 제외한다. afterglow.conf 전환 중에도 기존
    config.gpu.toml 오버라이드를 그대로 재사용할 수 있게 config.*.toml도 허용한다.
    """
    parent = base_path.parent
    patterns = [f"{base_path.stem}.*{base_path.suffix}"]
    if base_path.suffix != ".toml":
        patterns.append(f"{base_path.stem}.*.toml")
    if base_path.name == "afterglow.conf":
        patterns.append("config.*.toml")

    overrides: dict[Path, Path] = {}
    for pattern in patterns:
        for p in parent.glob(pattern):
            if p.name == base_path.name:
                continue
            if not p.is_file() or p.stat().st_size == 0:
                continue
            if p.name == "config.toml":
                continue
            overrides[p.resolve()] = p
    return [overrides[key] for key in sorted(overrides)]


def _load_toml() -> dict:
    """프로젝트 루트의 afterglow.conf/config.toml(+ 오버라이드)을 읽어 평탄화된 dict를 반환."""
    data = load_raw_toml()
    if not data:
        return {}

    flat: dict = {}
    ost = data.get("openstack", {})
    flat["os_auth_url"] = ost.get("auth_url", "")
    flat["os_username"] = ost.get("username", "")
    flat["os_password"] = ost.get("password", "")
    flat["os_project_name"] = ost.get("project_name", "admin")
    flat["os_project_domain_name"] = ost.get("project_domain_name", "Default")
    flat["os_user_domain_name"] = ost.get("user_domain_name", "Default")
    flat["os_region_name"] = ost.get("region_name", "RegionOne")
    flat["os_interface"] = ost.get("interface", "internal")
    flat["os_insecure"] = ost.get("insecure", False)
    flat["os_cacert"] = ost.get("cacert", "")
    flat["os_manila_endpoint"] = ost.get("manila_endpoint", "")
    flat["os_swift_endpoint"] = ost.get("swift_endpoint", "")
    flat["os_swift_upload_timeout"] = ost.get("swift_upload_timeout", 1800)
    flat["os_trash_retention_days"] = ost.get("trash_retention_days", 30)
    flat["os_manila_share_network_id"] = ost.get("manila_share_network_id", "")
    flat["os_manila_share_type"] = ost.get("manila_share_type", "cephfs")
    flat["os_manila_nfs_share_type"] = ost.get("manila_nfs_share_type", "nfstype")
    flat["manila_nfs_root_squash"] = ost.get("manila_nfs_root_squash", True)
    flat["manila_nfs_sec_flavor"] = ost.get("manila_nfs_sec_flavor", "sys")
    flat["manila_cephx_key_timeout_seconds"] = ost.get("manila_cephx_key_timeout_seconds", 300)
    flat["ceph_monitors"] = ost.get("ceph_monitors", "")
    flat["os_service_project_id"] = ost.get("service_project_id", "")

    app = data.get("app", {})
    flat["backend_port"] = app.get("backend_port", 8000)
    flat["frontend_port"] = app.get("frontend_port", 3080)
    flat["secret_key"] = app.get("secret_key", "change-me-in-production")
    flat["refresh_interval_ms"] = app.get("refresh_interval_ms", 5000)
    flat["site_name"] = app.get("site_name", "Afterglow")
    flat["site_description"] = app.get("site_description", "OpenStack VM + OverlayFS 배포 플랫폼")
    flat["logo_path"] = app.get("logo_path", "/logo.png")
    flat["logo_dark_path"] = app.get("logo_dark_path", "/logo-white.png")
    flat["logo_light_path"] = app.get("logo_light_path", "/logo-dark.png")
    flat["favicon_path"] = app.get("favicon_path", "/favicon.ico")
    flat["frontend_base_url"] = app.get("frontend_base_url", "")
    flat["public_api_base"] = app.get("public_api_base", "")

    cache = data.get("cache", {})
    flat["redis_url"] = cache.get("redis_url", "redis://localhost:6379/0")
    flat["cache_ttl_seconds"] = cache.get("default_ttl_seconds", 30)
    flat["cache_ttl_fast"] = cache.get("ttl_fast", 15)
    flat["cache_ttl_normal"] = cache.get("ttl_normal", cache.get("default_ttl_seconds", 30))
    flat["cache_ttl_slow"] = cache.get("ttl_slow", 60)
    flat["cache_ttl_static"] = cache.get("ttl_static", 300)
    flat["cache_backend"] = cache.get("backend", "redis")
    flat["sentinel_enabled"] = cache.get("sentinel_enabled", False)
    flat["sentinel_master_name"] = cache.get("sentinel_master_name", "mymaster")
    flat["sentinel_hosts"] = cache.get("sentinel_hosts", "")
    flat["cache_dynamic_threshold_low"] = cache.get("dynamic_threshold_low", 5)
    flat["cache_dynamic_threshold_high"] = cache.get("dynamic_threshold_high", 20)
    flat["cache_ttl_identity_stable"] = cache.get("ttl_identity_stable", 86400)
    flat["cache_ttl_catalog_slow"] = cache.get("ttl_catalog_slow", 900)
    flat["cache_ttl_project_meta"] = cache.get("ttl_project_meta", 300)
    flat["cache_ttl_operational_live"] = cache.get("ttl_operational_live", 30)
    flat["cache_ttl_admin_overview"] = cache.get("ttl_admin_overview", 60)
    flat["cache_ttl_auth_token"] = cache.get("ttl_auth_token", 60)

    svc = data.get("services", {})
    flat["service_magnum_enabled"] = svc.get("magnum", False)
    flat["service_manila_enabled"] = svc.get("manila", False)
    flat["service_zun_enabled"] = svc.get("zun", False)
    flat["service_k3s_enabled"] = svc.get("k3s", False)
    flat["service_trove_enabled"] = svc.get("trove", False)
    flat["service_swift_enabled"] = svc.get("swift", False)
    flat["service_barbican_enabled"] = svc.get("barbican", False)
    flat["service_vpn_enabled"] = svc.get("vpn", False)
    flat["service_chat_enabled"] = svc.get("chat", False)

    k3s = data.get("k3s", {})
    flat["k3s_version"] = k3s.get("version", "v1.34.6+k3s1")
    flat["k3s_server_flavor_id"] = k3s.get("server_flavor_id", "")
    flat["k3s_default_agent_flavor_id"] = k3s.get("default_agent_flavor_id", "")
    flat["k3s_server_image_id"] = k3s.get("server_image_id", "")
    flat["k3s_callback_base_url"] = k3s.get("callback_base_url", "")
    flat["k3s_kubeconfig_encryption_key"] = k3s.get("kubeconfig_encryption_key", "")
    flat["k3s_boot_volume_size_gb"] = k3s.get("boot_volume_size_gb", 30)
    flat["k3s_occm_enabled"] = k3s.get("occm_enabled", False)
    flat["k3s_occm_image"] = k3s.get(
        "occm_image",
        "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.34.1",
    )
    flat["k3s_occm_floating_network_id"] = k3s.get("occm_floating_network_id", "")
    flat["k3s_occm_public_network_name"] = k3s.get("occm_public_network_name", "")
    # Cinder CSI
    flat["k3s_cinder_csi_enabled"] = k3s.get("cinder_csi_enabled", False)
    flat["k3s_cinder_csi_image"] = k3s.get("cinder_csi_image", "registry.k8s.io/provider-os/cinder-csi-plugin:v1.34.1")
    flat["k3s_cinder_csi_default_az"] = k3s.get("cinder_csi_default_az", "nova")
    # Manila CSI
    flat["k3s_manila_csi_enabled"] = k3s.get("manila_csi_enabled", False)
    flat["k3s_manila_csi_image"] = k3s.get("manila_csi_image", "registry.k8s.io/provider-os/manila-csi-plugin:v1.34.1")
    flat["k3s_manila_csi_nfs_image"] = k3s.get("manila_csi_nfs_image", "registry.k8s.io/sig-storage/nfsplugin:v4.9.0")
    flat["k3s_manila_csi_share_protocol"] = k3s.get("manila_csi_share_protocol", "NFS")
    # Keystone Auth
    flat["k3s_keystone_auth_enabled"] = k3s.get("keystone_auth_enabled", False)
    flat["k3s_keystone_auth_image"] = k3s.get(
        "keystone_auth_image", "registry.k8s.io/provider-os/k8s-keystone-auth:v1.34.1"
    )
    flat["k3s_keystone_auth_policy"] = k3s.get("keystone_auth_policy", "")
    # Octavia Ingress
    flat["k3s_octavia_ingress_enabled"] = k3s.get("octavia_ingress_enabled", False)
    flat["k3s_octavia_ingress_image"] = k3s.get(
        "octavia_ingress_image",
        "registry.k8s.io/provider-os/octavia-ingress-controller:v1.34.1",
    )
    flat["k3s_octavia_ingress_subnet_id"] = k3s.get("octavia_ingress_subnet_id", "")
    flat["k3s_octavia_ingress_floating_network_id"] = k3s.get("octavia_ingress_floating_network_id", "")
    # Barbican KMS
    flat["k3s_barbican_kms_enabled"] = k3s.get("barbican_kms_enabled", False)
    flat["k3s_barbican_kms_image"] = k3s.get(
        "barbican_kms_image", "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    )
    flat["k3s_barbican_kms_kek_id"] = k3s.get("barbican_kms_kek_id", "")
    # LB 네트워크 분리: OCCM Service LB 공통 VIP 서브넷
    flat["k3s_lb_subnet_id"] = k3s.get("lb_subnet_id", "")
    # API LB VIP 네트워크 (모드 A: provider 네트워크 직접 지정)
    flat["k3s_api_lb_vip_network_id"] = k3s.get("api_lb_vip_network_id", "")
    # API LB Floating IP 외부 네트워크 (모드 B: FIP 할당)
    flat["k3s_api_lb_floating_network_id"] = k3s.get("api_lb_floating_network_id", "")
    # FCOS (Fedora CoreOS) 이미지 ID
    flat["k3s_fcos_image_id"] = k3s.get("fcos_image_id", "")
    # 인증서 회전
    flat["k3s_cert_rotation_node_timeout_sec"] = k3s.get("cert_rotation_node_timeout_sec", 300)
    flat["k3s_cert_rotation_job_image"] = k3s.get(
        "cert_rotation_job_image",
        "registry.k8s.io/util-linux/util-linux:latest",
    )
    # Stampede 오토스케일
    flat["k3s_stampede_enabled"] = k3s.get("stampede_enabled", False)
    flat["k3s_stampede_interval"] = k3s.get("stampede_interval", 60)
    flat["k3s_stampede_scale_down_threshold"] = k3s.get("stampede_scale_down_threshold", 0.5)
    flat["k3s_stampede_scale_down_window"] = k3s.get("stampede_scale_down_window", 600)
    flat["k3s_stampede_scale_up_cooldown"] = k3s.get("stampede_scale_up_cooldown", 120)
    flat["k3s_stampede_scale_down_cooldown"] = k3s.get("stampede_scale_down_cooldown", 300)
    flat["k3s_stampede_resource_headroom_factor"] = k3s.get("stampede_resource_headroom_factor", 0.3)

    wr = data.get("worker_runtime", {})
    wr_workers = wr.get("workers", {})
    wr_drover = wr_workers.get("drover", {})
    wr_notion = wr_workers.get("notion_worker", {})
    wr_docker = wr.get("docker", {})
    wr_k8s = wr.get("kubernetes", {})
    flat["worker_runtime_mode"] = wr.get("mode", "static")
    flat["worker_runtime_reconcile_interval"] = wr.get("reconcile_interval", 30)
    flat["worker_runtime_fail_closed"] = wr.get("fail_closed", True)
    flat["worker_runtime_drover_enabled"] = wr_drover.get("enabled", True)
    flat["worker_runtime_drover_desired_replicas"] = wr_drover.get("desired_replicas", 1)
    flat["worker_runtime_drover_max_replicas"] = wr_drover.get("max_replicas", 1)
    flat["worker_runtime_drover_module"] = wr_drover.get("module", "app.worker")
    flat["worker_runtime_notion_worker_enabled"] = wr_notion.get("enabled", True)
    flat["worker_runtime_notion_worker_desired_replicas"] = wr_notion.get("desired_replicas", 1)
    flat["worker_runtime_notion_worker_max_replicas"] = wr_notion.get("max_replicas", 1)
    flat["worker_runtime_notion_worker_module"] = wr_notion.get("module", "app.notion_worker")
    flat["worker_runtime_docker_socket_path"] = wr_docker.get("socket_path", "")
    flat["worker_runtime_docker_image"] = wr_docker.get("image", "")
    flat["worker_runtime_docker_network"] = wr_docker.get("network", "")
    flat["worker_runtime_docker_config_mount"] = wr_docker.get("config_mount", "/app/afterglow.conf")
    flat["worker_runtime_docker_config_host_path"] = wr_docker.get("config_host_path", "")
    flat["worker_runtime_docker_gpu_config_mount"] = wr_docker.get("gpu_config_mount", "/app/config.gpu.toml")
    flat["worker_runtime_docker_gpu_config_host_path"] = wr_docker.get("gpu_config_host_path", "")
    flat["worker_runtime_docker_logs_mount"] = wr_docker.get("logs_mount", "/app/logs")
    flat["worker_runtime_docker_logs_host_path"] = wr_docker.get("logs_host_path", "")
    flat["worker_runtime_docker_env_allowlist"] = wr_docker.get(
        "env_allowlist",
        (
            "AFTERGLOW_ENV,AFTERGLOW_ALLOW_INSECURE,SECRET_KEY,OS_PASSWORD,DATABASE_URL,"
            "K3S_KUBECONFIG_ENCRYPTION_KEY,PROMETHEUS_PASSWORD,GITLAB_OIDC_CLIENT_SECRET,"
            "NOTION_CONFIG_ENCRYPTION_KEY"
        ),
    )
    flat["worker_runtime_kubernetes_namespace"] = wr_k8s.get("namespace", "afterglow")
    flat["worker_runtime_kubernetes_service_account_token_path"] = wr_k8s.get(
        "service_account_token_path", "/var/run/secrets/kubernetes.io/serviceaccount/token"
    )
    flat["worker_runtime_kubernetes_service_account_ca_path"] = wr_k8s.get(
        "service_account_ca_path", "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    )
    flat["worker_runtime_kubernetes_manage_deployments"] = wr_k8s.get("manage_deployments", False)

    gpu = data.get("gpu", {})
    flat["gpu_available_visible"] = gpu.get("available_visible", False)

    sess = data.get("session", {})
    flat["session_timeout_seconds"] = sess.get("timeout_seconds", 3600)
    flat["jwt_access_ttl"] = sess.get("jwt_access_ttl", 900)
    flat["jwt_refresh_ttl"] = sess.get("jwt_refresh_ttl", 604800)
    flat["token_ip_binding_mode"] = sess.get("token_ip_binding_mode", "subnet")

    nv = data.get("nova", {})
    flat["default_network_id"] = nv.get("default_network_id", "")
    flat["default_network_enabled"] = nv.get("default_network_enabled", True)
    flat["default_network_cidr"] = nv.get("default_network_cidr", "192.168.0.0/24")
    flat["default_network_external_id"] = nv.get("default_network_external_id", "")
    flat["default_availability_zone"] = nv.get("default_availability_zone", "nova")
    flat["boot_volume_size_gb"] = nv.get("boot_volume_size_gb", 20)
    flat["upper_volume_size_gb"] = nv.get("upper_volume_size_gb", 50)
    flat["server_image_id"] = nv.get("server_image_id", "")

    builder = data.get("builder", {})
    flat["builder_image_id"] = builder.get("image_id", "")
    flat["builder_ubuntu_18_04_image_id"] = builder.get("ubuntu_18_04_image_id", "")
    flat["builder_ubuntu_20_04_image_id"] = builder.get("ubuntu_20_04_image_id", "")
    flat["builder_ubuntu_22_04_image_id"] = builder.get("ubuntu_22_04_image_id", "")
    flat["builder_ubuntu_24_04_image_id"] = builder.get("ubuntu_24_04_image_id", "")
    flat["builder_flavor_id"] = builder.get("flavor_id", "")
    flat["builder_network_id"] = builder.get("network_id", "")
    flat["builder_ssh_user"] = builder.get("ssh_user", "ubuntu")
    flat["builder_ssh_key_path"] = builder.get("ssh_key_path", "/etc/afterglow/ssh/builder.key")
    flat["builder_floating_network_id"] = builder.get("floating_network_id", "")
    flat["builder_build_timeout"] = builder.get("build_timeout", 3600)
    flat["builder_layer_share_size_gb"] = builder.get("layer_share_size_gb", 20)

    union = data.get("union", {})
    flat["union_layer_store_rw_share_id"] = union.get("layer_store_rw_share_id", "")
    flat["union_layer_store_ro_share_id"] = union.get("layer_store_ro_share_id", "")
    flat["union_manifest_store_share_id"] = union.get("manifest_store_share_id", "")

    vpn = data.get("vpn", {})
    flat["vpn_provider_network_id"] = vpn.get("provider_network_id", "")
    flat["vpn_flavor_name"] = vpn.get("flavor_name", "cpu.1c_2g")
    flat["vpn_flavor_id"] = vpn.get("flavor_id", "")
    flat["vpn_image_id"] = vpn.get("image_id", "")
    flat["vpn_floating_network_id"] = vpn.get("floating_network_id", "")
    flat["vpn_callback_base_url"] = vpn.get("callback_base_url", "")
    flat["vpn_key_name"] = vpn.get("key_name", "")
    flat["vpn_default_tunnel_cidr"] = vpn.get("default_tunnel_cidr", "10.8.0.0/24")
    flat["vpn_default_listen_port"] = vpn.get("default_listen_port", 51820)

    mon = data.get("monitoring", {})
    flat["prometheus_base_url"] = mon.get("prometheus_base_url", "http://prometheus:9090")
    flat["prometheus_username"] = mon.get("prometheus_username", "")
    flat["prometheus_password"] = mon.get("prometheus_password", "")
    flat["monitoring_sd_token"] = mon.get("sd_token", "")
    flat["monitoring_scrape_cidr"] = mon.get("scrape_cidr", "")
    flat["monitoring_auto_sg_enabled"] = mon.get("auto_sg_enabled", True)
    flat["node_exporter_sg_name"] = mon.get("node_exporter_sg_name", "node_exporter")
    flat["dcgm_exporter_sg_name"] = mon.get("dcgm_exporter_sg_name", "dcgm_exporter")
    flat["node_exporter_port"] = mon.get("node_exporter_port", 9100)
    flat["dcgm_exporter_port"] = mon.get("dcgm_exporter_port", 9400)
    flat["libvirt_exporter_port"] = mon.get("libvirt_exporter_port", 9177)
    flat["gpu_flavor_prefix"] = mon.get("gpu_flavor_prefix", "gpu.")
    flat["grafana_base_url"] = mon.get("grafana_base_url", "")
    dashboards = mon.get("dashboards", {})
    flat["grafana_dashboard_node_uid"] = dashboards.get("node_uid", "afterglow-node")
    flat["grafana_dashboard_rabbitmq_uid"] = dashboards.get("rabbitmq_uid", "afterglow-rabbitmq")
    flat["grafana_dashboard_mysqld_uid"] = dashboards.get("mysqld_uid", "afterglow-mysqld")
    flat["grafana_dashboard_memcached_uid"] = dashboards.get("memcached_uid", "afterglow-memcached")
    flat["grafana_dashboard_etcd_uid"] = dashboards.get("etcd_uid", "afterglow-etcd")
    flat["grafana_dashboard_haproxy_uid"] = dashboards.get("haproxy_uid", "afterglow-haproxy")
    flat["grafana_dashboard_libvirt_uid"] = dashboards.get("libvirt_uid", "afterglow-libvirt")
    flat["grafana_dashboard_openstack_uid"] = dashboards.get("openstack_uid", "afterglow-openstack")
    flat["grafana_dashboard_ceph_uid"] = dashboards.get("ceph_uid", "afterglow-ceph")
    flat["grafana_dashboard_instance_cpu_uid"] = dashboards.get("instance_cpu_uid", "afterglow-instance-cpu")
    flat["grafana_dashboard_instance_gpu_uid"] = dashboards.get("instance_gpu_uid", "afterglow-instance-gpu")

    chat = data.get("chat", {})
    flat["librechat_mongo_url"] = chat.get("mongo_url", "")
    flat["librechat_base_url"] = chat.get("base_url", "")

    notion = data.get("notion", {})
    flat["notion_config_encryption_key"] = notion.get("config_encryption_key", "")

    security = data.get("security", {})
    flat["admin_legacy_project_policy"] = security.get("admin_legacy_project_policy", False)
    flat["login_max_attempts"] = security.get("login_max_attempts", 10)
    flat["login_lockout_seconds"] = security.get("login_lockout_seconds", 300)
    flat["login_backoff_base"] = security.get("login_backoff_base", 2)

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
    flat["database_connect_timeout"] = db.get("connect_timeout", 10)
    flat["database_pool_timeout"] = db.get("pool_timeout", 10)
    flat["database_unhealthy_seconds"] = db.get("unhealthy_seconds", 15)
    flat["database_db_auto_backup_cron"] = db.get("db_auto_backup_cron", "0 3 * * *")

    smtp = data.get("smtp", {})
    flat["smtp_enabled"] = smtp.get("enabled", False)
    flat["smtp_host"] = smtp.get("host", "")
    flat["smtp_port"] = smtp.get("port", 587)
    flat["smtp_username"] = smtp.get("username", "")
    flat["smtp_password"] = smtp.get("password", "")
    flat["smtp_from_address"] = smtp.get("from_address", "noreply@afterglow.example.com")
    flat["smtp_from_name"] = smtp.get("from_name", "Afterglow")
    flat["smtp_use_tls"] = smtp.get("use_tls", True)
    flat["smtp_timeout_seconds"] = smtp.get("timeout_seconds", 10)
    smtp_inv = smtp.get("invitation", {})
    flat["smtp_invitation_token_expiry_days"] = smtp_inv.get("token_expiry_days", 7)

    cors = data.get("cors", {})
    flat["cors_origins"] = cors.get("origins", "http://localhost:3080,http://localhost")

    log = data.get("logging", {})
    flat["log_file_path"] = log.get("log_file_path", "/app/logs/afterglow-backend.log")
    flat["log_level"] = log.get("log_level", "INFO")
    flat["log_max_bytes"] = log.get("max_bytes", 52428800)
    flat["log_backup_count"] = log.get("backup_count", 5)
    flat["log_rotation_type"] = log.get("rotation_type", "size")
    flat["log_rotation_when"] = log.get("rotation_when", "midnight")
    flat["log_rotation_interval"] = log.get("rotation_interval", 1)

    return flat


class Settings(BaseSettings):
    # OpenStack 인증
    os_auth_url: str = ""
    os_username: str = ""
    os_password: str = ""
    os_project_name: str = "admin"
    os_project_domain_name: str = "Default"
    os_user_domain_name: str = "Default"
    os_region_name: str = "RegionOne"
    os_interface: str = "internal"
    os_insecure: bool = False
    os_cacert: str = ""

    # Manila 설정
    os_service_project_id: str = (
        ""  # Union Mount 빌더/share 전용 service 프로젝트 UUID. 미설정 시 prebuilt 경로 fail-fast.
    )
    os_manila_endpoint: str = ""
    # Swift 설정
    os_swift_endpoint: str = ""
    os_swift_upload_timeout: int = 1800  # 대용량 업로드용 타임아웃 (초)
    os_trash_retention_days: int = 30  # 휴지통 보관 기간 (일). 만료 후 자동 영구 삭제.
    # S3 Direct Upload 설정 (Ceph RGW S3 endpoint 대상)
    os_s3_endpoint: str = "https://s3.dmslab.re.kr"
    upload_part_size_mb: int = 50
    upload_url_expires_sec: int = 3600
    upload_tx_ttl_sec: int = 86400
    os_manila_share_network_id: str = ""
    os_manila_share_type: str = "cephfs"
    os_manila_nfs_share_type: str = "nfstype"
    manila_nfs_root_squash: bool = True  # NFS access rule root_squash 강제 (보안 기본값)
    manila_nfs_sec_flavor: str = "sys"  # NFS 인증 flavor: "sys"(기본) | "krb5"(Kerberos)
    manila_cephx_key_timeout_seconds: int = 300  # CephX key 발급 폴링 최대 대기 (초)

    # Ceph 모니터 (cloud-init CephFS 마운트용)
    ceph_monitors: str = ""

    # 앱 설정
    backend_port: int = 8000
    frontend_port: int = 3080
    secret_key: str = "change-me-in-production"
    # object-storage 업로드 단일 파일 최대 크기 (GiB). 0 또는 음수 = 사실상 무제한(기존 100GiB cap).
    app_max_upload_gb: int = 10
    # rate-limit / 클라이언트 IP 추출 시 신뢰할 reverse proxy CIDR (쉼표 구분).
    # 비어 있으면 X-Forwarded-For / X-Real-IP 헤더를 모두 무시 → 직접 연결 IP 사용.
    # 운영(K8s/HAProxy) 에서는 ingress/HAProxy 의 pod CIDR 을 명시적으로 추가해야 한다.
    trusted_proxies: str = "127.0.0.1/32,::1/128"

    # CORS 허용 origin (쉼표 구분)
    cors_origins: str = "http://localhost:3080,http://localhost"
    refresh_interval_ms: int = 5000
    site_name: str = "Afterglow"
    site_description: str = "OpenStack VM + OverlayFS 배포 플랫폼"
    logo_path: str = "/logo.png"
    logo_dark_path: str = "/logo-white.png"
    logo_light_path: str = "/logo-dark.png"
    favicon_path: str = "/favicon.ico"

    # Redis 캐시
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 30
    cache_ttl_fast: int = 15
    cache_ttl_normal: int = 30
    cache_ttl_slow: int = 60
    cache_ttl_static: int = 300
    # 캐시 백엔드: "redis" | "valkey" (v1 동일 클라이언트, v2 에서 Memcached 추가 시 확장)
    cache_backend: Literal["redis", "valkey"] = "redis"
    # Redis Sentinel HA
    sentinel_enabled: bool = False
    sentinel_master_name: str = "mymaster"
    sentinel_hosts: str = ""  # 콤마 구분 "host:port" 목록 (예: sentinel-a:26379,sentinel-b:26379)
    # Dynamic TTL 조정 임계치 (시간당 mutation 횟수)
    cache_dynamic_threshold_low: int = 5
    cache_dynamic_threshold_high: int = 20
    # 3-tier TTL 카테고리 (Phase B)
    cache_ttl_identity_stable: int = 86400  # 개인 프로필, role/group 멤버십
    cache_ttl_catalog_slow: int = 900  # flavors, image 메타, 데이터스토어
    cache_ttl_project_meta: int = 300  # keypair, SG 정의, 네트워크 메타
    cache_ttl_operational_live: int = 30  # instances/volumes/FIP/컨테이너 상태
    cache_ttl_admin_overview: int = 60  # admin 토폴로지, 하이퍼바이저
    cache_ttl_auth_token: int = 60  # Keystone 토큰 검증 결과

    # 선택적 서비스
    service_magnum_enabled: bool = False
    service_manila_enabled: bool = False
    service_zun_enabled: bool = False
    service_k3s_enabled: bool = False
    service_trove_enabled: bool = False
    service_swift_enabled: bool = False
    service_barbican_enabled: bool = False
    service_vpn_enabled: bool = False  # WireGuard VPN 게이트웨이 (활성화 시 [vpn] 섹션 설정도 필요)
    service_chat_enabled: bool = False  # AI 채팅(LibreChat 임베드) (활성화 시 [chat] 섹션 설정도 필요)

    # k3s 설정
    k3s_version: str = "v1.34.6+k3s1"
    k3s_server_flavor_id: str = ""
    k3s_default_agent_flavor_id: str = ""
    k3s_server_image_id: str = ""
    k3s_callback_base_url: str = ""
    k3s_kubeconfig_encryption_key: str = ""
    k3s_boot_volume_size_gb: int = 30
    k3s_occm_enabled: bool = False
    k3s_occm_image: str = "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.34.1"
    k3s_occm_floating_network_id: str = ""
    k3s_occm_public_network_name: str = ""
    # Cinder CSI
    k3s_cinder_csi_enabled: bool = False
    k3s_cinder_csi_image: str = "registry.k8s.io/provider-os/cinder-csi-plugin:v1.34.1"
    k3s_cinder_csi_default_az: str = "nova"
    # Manila CSI
    k3s_manila_csi_enabled: bool = False
    k3s_manila_csi_image: str = "registry.k8s.io/provider-os/manila-csi-plugin:v1.34.1"
    k3s_manila_csi_nfs_image: str = "registry.k8s.io/sig-storage/nfsplugin:v4.9.0"
    k3s_manila_csi_share_protocol: str = "NFS"
    # Keystone Auth
    k3s_keystone_auth_enabled: bool = False
    k3s_keystone_auth_image: str = "registry.k8s.io/provider-os/k8s-keystone-auth:v1.34.1"
    k3s_keystone_auth_policy: str = ""
    # Octavia Ingress
    k3s_octavia_ingress_enabled: bool = False
    k3s_octavia_ingress_image: str = "registry.k8s.io/provider-os/octavia-ingress-controller:v1.34.1"
    k3s_octavia_ingress_subnet_id: str = ""
    k3s_octavia_ingress_floating_network_id: str = ""
    # Barbican KMS
    k3s_barbican_kms_enabled: bool = False
    k3s_barbican_kms_image: str = "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    k3s_barbican_kms_kek_id: str = ""
    # LB 네트워크 분리: OCCM Service LB VIP 서브넷 (미설정 시 클러스터 네트워크의 첫 서브넷)
    k3s_lb_subnet_id: str = ""
    # API LB VIP 네트워크 (모드 A: provider 네트워크 직접 지정, 설정 시 FIP 불필요)
    k3s_api_lb_vip_network_id: str = ""
    # API LB Floating IP 외부 네트워크 (모드 B: FIP 할당, 미설정 시 k3s_occm_floating_network_id fallback)
    k3s_api_lb_floating_network_id: str = ""
    # FCOS (Fedora CoreOS) 이미지 ID (os_type=fcos 클러스터에 사용)
    k3s_fcos_image_id: str = ""
    # 인증서 회전
    k3s_cert_rotation_node_timeout_sec: int = 300
    k3s_cert_rotation_job_image: str = "registry.k8s.io/util-linux/util-linux:latest"
    # Stampede 오토스케일
    k3s_stampede_enabled: bool = False
    k3s_stampede_interval: int = 60
    k3s_stampede_scale_down_threshold: float = 0.5
    k3s_stampede_scale_down_window: int = 600
    k3s_stampede_scale_up_cooldown: int = 120
    k3s_stampede_scale_down_cooldown: int = 300
    k3s_stampede_resource_headroom_factor: float = 0.3

    # Background worker runtime manager
    worker_runtime_mode: Literal["static", "docker", "kubernetes"] = "static"
    worker_runtime_reconcile_interval: int = 30
    worker_runtime_fail_closed: bool = True
    worker_runtime_drover_enabled: bool = True
    worker_runtime_drover_desired_replicas: int = 1
    worker_runtime_drover_max_replicas: int = 1
    worker_runtime_drover_module: str = "app.worker"
    worker_runtime_notion_worker_enabled: bool = True
    worker_runtime_notion_worker_desired_replicas: int = 1
    worker_runtime_notion_worker_max_replicas: int = 1
    worker_runtime_notion_worker_module: str = "app.notion_worker"
    worker_runtime_docker_socket_path: str = ""
    worker_runtime_docker_image: str = ""
    worker_runtime_docker_network: str = ""
    worker_runtime_docker_config_mount: str = "/app/afterglow.conf"
    worker_runtime_docker_config_host_path: str = ""
    worker_runtime_docker_gpu_config_mount: str = "/app/config.gpu.toml"
    worker_runtime_docker_gpu_config_host_path: str = ""
    worker_runtime_docker_logs_mount: str = "/app/logs"
    worker_runtime_docker_logs_host_path: str = ""
    worker_runtime_docker_env_allowlist: str = (
        "AFTERGLOW_ENV,AFTERGLOW_ALLOW_INSECURE,SECRET_KEY,OS_PASSWORD,DATABASE_URL,"
        "K3S_KUBECONFIG_ENCRYPTION_KEY,PROMETHEUS_PASSWORD,GITLAB_OIDC_CLIENT_SECRET,"
        "NOTION_CONFIG_ENCRYPTION_KEY"
    )
    worker_runtime_kubernetes_namespace: str = "afterglow"
    worker_runtime_kubernetes_service_account_token_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    worker_runtime_kubernetes_service_account_ca_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    worker_runtime_kubernetes_manage_deployments: bool = False

    @field_validator(
        "worker_runtime_reconcile_interval",
        "worker_runtime_drover_desired_replicas",
        "worker_runtime_drover_max_replicas",
        "worker_runtime_notion_worker_desired_replicas",
        "worker_runtime_notion_worker_max_replicas",
    )
    @classmethod
    def validate_worker_runtime_counts(cls, v: int) -> int:
        if v < 0:
            raise ValueError("worker runtime replica counts and intervals must be non-negative")
        return v

    # Union Mount 레이어 시스템 — Manila share ID
    union_layer_store_rw_share_id: str = ""  # layer-store-rw (Builder 전용 RW)
    union_layer_store_ro_share_id: str = ""  # layer-store-ro (User VM RO)
    union_manifest_store_share_id: str = ""  # manifest-store
    union_cephx_rotate_hours: int = 24  # CephX 키 자동 회전 주기 (0이면 비활성)
    union_auto_egress_sg_enabled: bool = True  # Union VM에 egress SG 자동 attach
    union_egress_sg_name: str = "union-egress-default"  # 자동 생성/재사용할 SG 이름

    # WireGuard VPN 게이트웨이 (Phase 1)
    vpn_provider_network_id: str = ""  # VPN VM이 부팅될 provider 네트워크 ID
    vpn_flavor_name: str = "cpu.1c_2g"  # flavor 이름으로 해석 (flavor_id override 가능)
    vpn_flavor_id: str = ""  # 설정 시 이름 조회 없이 바로 사용
    vpn_image_id: str = ""  # VPN VM 부팅 이미지 ID (Ubuntu 22.04+)
    vpn_floating_network_id: str = ""  # 설정 시 FIP 할당, 미설정 시 provider fixed IP를 endpoint로 사용
    vpn_callback_base_url: str = ""  # 에이전트가 콜백할 백엔드 URL (예: http://10.0.0.1:8000)
    vpn_key_name: str = ""  # VPN VM에 연결할 Nova keypair 이름 (옵션)
    vpn_default_tunnel_cidr: str = "10.8.0.0/24"  # WireGuard 터널 서브넷 기본값
    vpn_default_listen_port: int = 51820  # WireGuard UDP 리슨 포트 기본값

    # 모니터링 (Prometheus + Grafana — Option A, label-based 프로젝트 격리)
    monitoring_auto_sg_enabled: bool = True  # 프로젝트/인스턴스 생성 시 monitoring SG 자동 attach
    node_exporter_sg_name: str = "node_exporter"  # node_exporter ingress SG 이름 (tcp/9100)
    dcgm_exporter_sg_name: str = "dcgm_exporter"  # dcgm_exporter ingress SG 이름 (tcp/9400, GPU 전용)
    node_exporter_port: int = 9100  # VM에 설치된 node_exporter 포트
    dcgm_exporter_port: int = 9400  # GPU VM의 dcgm_exporter 포트
    libvirt_exporter_port: int = 9177  # compute 노드 libvirt_exporter 포트 (kolla enable_prometheus_libvirt_exporter)
    gpu_flavor_prefix: str = "gpu."  # GPU 노드로 판별할 flavor 이름 prefix
    monitoring_scrape_cidr: str = ""  # Prometheus scrape CIDR (예: 10.0.0.0/8). 미설정 시 ValueError
    monitoring_sd_token: str = ""  # /api/sd/prometheus/targets 인증 토큰
    grafana_base_url: str = ""  # Grafana 외부 URL (예: https://grafana.example.com)
    grafana_dashboard_node_uid: str = "afterglow-node"
    grafana_dashboard_rabbitmq_uid: str = "afterglow-rabbitmq"
    grafana_dashboard_mysqld_uid: str = "afterglow-mysqld"
    grafana_dashboard_memcached_uid: str = "afterglow-memcached"
    grafana_dashboard_etcd_uid: str = "afterglow-etcd"
    grafana_dashboard_haproxy_uid: str = "afterglow-haproxy"
    grafana_dashboard_libvirt_uid: str = "afterglow-libvirt"
    grafana_dashboard_openstack_uid: str = "afterglow-openstack"
    grafana_dashboard_ceph_uid: str = "afterglow-ceph"
    grafana_dashboard_instance_cpu_uid: str = "afterglow-instance-cpu"
    grafana_dashboard_instance_gpu_uid: str = "afterglow-instance-gpu"
    # Prometheus 서버 주소. 우선순위: 환경변수 PROMETHEUS_BASE_URL > afterglow.conf/config.toml [monitoring].prometheus_base_url > 기본값
    prometheus_base_url: str = "http://prometheus:9090"
    prometheus_username: str = ""  # basic auth 미사용 시 빈 문자열
    prometheus_password: str = ""

    # LibreChat 임베드 연동 (기존 인스턴스 읽기 전용 조회)
    librechat_mongo_url: str = ""  # LibreChat MongoDB 읽기 전용 접속 URL (secret.yaml에서 주입)
    librechat_base_url: str = ""  # LibreChat 외부 URL (예: https://chat.dmslab.re.kr)

    # Notion 연동
    notion_config_encryption_key: str = ""  # 미설정 시 k3s_kubeconfig_encryption_key 재사용

    # GPU
    gpu_available_visible: bool = False  # true 시 사용자에게 GPU 가용량 API 노출

    # 세션 관리
    session_timeout_seconds: int = 3600
    jwt_access_ttl: int = 900  # access JWT 수명 (초), 기본 15분
    jwt_refresh_ttl: int = 604800  # refresh JWT 수명 (초), 기본 7일
    token_ip_binding_mode: str = "subnet"  # off | log | subnet | strict

    @field_validator("token_ip_binding_mode")
    @classmethod
    def validate_binding_mode(cls, v: str) -> str:
        _VALID_MODES = {"off", "log", "subnet", "strict"}
        if v not in _VALID_MODES:
            raise ValueError(f"token_ip_binding_mode={v!r} 은 유효하지 않습니다. 허용값: {sorted(_VALID_MODES)}")
        return v

    # 보안 정책
    # True: system:all role OR admin project+role 모두 system admin 인정 (마이그레이션 호환 모드)
    # False: system:all role만 system admin으로 인정 (자기복제 권한 상승 완전 차단)
    admin_legacy_project_policy: bool = False

    # 로그인 브루트포스 방어
    login_max_attempts: int = 10  # 잠금 임계값 (실패 횟수)
    login_lockout_seconds: int = 300  # 기본 잠금 시간 (초, 5분)
    login_backoff_base: int = 2  # 지수 백오프 밑수

    # Nova 기본값
    default_network_id: str = ""  # 레거시 폴백 (default_network_enabled=false 시 사용)
    default_network_enabled: bool = True  # 프로젝트별 Default 네트워크 자동 프로비저닝
    default_network_cidr: str = "192.168.0.0/24"  # Default 서브넷 CIDR
    default_network_external_id: str = ""  # 라우터 게이트웨이용 외부 네트워크 ID
    default_availability_zone: str = "nova"
    boot_volume_size_gb: int = 20
    upper_volume_size_gb: int = 50
    server_image_id: str = ""

    # 라이브러리 빌더 VM 설정
    builder_image_id: str = ""  # 빌더 VM 부팅 이미지 ID (Ubuntu 22.04+)
    builder_ubuntu_18_04_image_id: str = ""  # 레이어 workflow Ubuntu 18.04 canonical image ID
    builder_ubuntu_20_04_image_id: str = ""  # 레이어 workflow Ubuntu 20.04 canonical image ID
    builder_ubuntu_22_04_image_id: str = ""  # 레이어 workflow Ubuntu 22.04 canonical image ID
    builder_ubuntu_24_04_image_id: str = ""  # 레이어 workflow Ubuntu 24.04 canonical image ID
    builder_flavor_id: str = ""  # 빌더 VM 플레이버 ID
    builder_network_id: str = ""  # 빌더 VM 네트워크 ID (미지정 시 default_network_id 사용)
    builder_ssh_user: str = "ubuntu"  # Builder VM SSH 사용자
    builder_ssh_key_path: str = "/etc/afterglow/ssh/builder.key"  # SSH 개인키 경로
    builder_floating_network_id: str = ""  # Builder VM FIP 할당용 외부 네트워크 ID
    builder_build_timeout: int = 3600  # 빌드 SSH 명령 최대 대기 시간 (초)
    builder_layer_share_size_gb: int = 20  # 레이어별 동적 Manila NFS share 용량 (GB)

    # 데이터베이스 (MariaDB/MySQL, 선택적)
    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_auto_create_tables: bool = True
    database_connect_timeout: int = 10
    database_pool_timeout: int = 10
    database_unhealthy_seconds: int = 15
    database_db_auto_backup_cron: str = "0 3 * * *"

    # GitLab OIDC
    gitlab_oidc_enabled: bool = False
    gitlab_oidc_gitlab_url: str = ""
    gitlab_oidc_client_id: str = ""
    gitlab_oidc_client_secret: str = ""
    gitlab_oidc_idp_id: str = "gitlab"
    gitlab_oidc_protocol_id: str = "openid"
    gitlab_oidc_redirect_uri: str = ""
    gitlab_oidc_scopes: str = "openid email profile read_user"

    # SMTP 이메일 전송
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@afterglow.example.com"
    smtp_from_name: str = "Afterglow"
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 10
    smtp_invitation_token_expiry_days: int = 7

    # 프론트엔드 기본 URL (초대 이메일 링크 생성에 사용)
    frontend_base_url: str = ""
    # 브라우저 런타임 API Origin (비워두면 프론트엔드가 현재 호스트의 backend_port 사용)
    public_api_base: str = ""

    # 로깅 설정
    log_file_path: str = "/app/logs/afterglow-backend.log"
    log_level: str = "INFO"
    log_max_bytes: int = 52428800  # 50MB
    log_backup_count: int = 5
    log_rotation_type: str = "size"  # "size" | "time"
    log_rotation_when: str = "midnight"
    log_rotation_interval: int = 1

    @field_validator("os_auth_url", mode="after")
    @classmethod
    def _norm_auth_url(cls, v: str) -> str:
        from app.services._endpoint import normalize_keystone_url

        return normalize_keystone_url(v)

    @field_validator("os_manila_endpoint", "os_swift_endpoint", mode="after")
    @classmethod
    def _norm_service_endpoint(cls, v: str) -> str:
        from app.services._endpoint import normalize_endpoint

        return normalize_endpoint(v)

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
        env = os.environ.get("AFTERGLOW_ENV", "development").strip().lower()
        is_production = env == "production"
        insecure_flag = os.environ.get("AFTERGLOW_ALLOW_INSECURE", "").strip() == "1"

        # production 환경에서는 INSECURE 우회 자체를 금지 — 운영 부팅 실수 차단.
        if is_production and insecure_flag:
            raise ValueError(
                "AFTERGLOW_ALLOW_INSECURE=1 must NOT be set when AFTERGLOW_ENV=production. "
                "Provide a real SECRET_KEY (and other secrets) instead of bypassing the check."
            )

        if self.secret_key == "change-me-in-production":
            if is_production:
                raise ValueError(
                    "SECRET_KEY is set to the default value 'change-me-in-production' "
                    "while AFTERGLOW_ENV=production. Refusing to start with an insecure key."
                )
            if insecure_flag:
                logger.warning(
                    "SECRET_KEY is set to the default insecure value. "
                    "AFTERGLOW_ALLOW_INSECURE=1 is set — this must NOT be used in production."
                )
            else:
                raise ValueError(
                    "SECRET_KEY is set to the default value 'change-me-in-production'. "
                    "Set a strong random value in afterglow.conf [app] secret_key or SECRET_KEY env var. "
                    "To override this check in development, set AFTERGLOW_ALLOW_INSECURE=1."
                )
        elif len(self.secret_key) < 32:
            # 비기본이어도 약한(짧은) 키는 production 부팅을 거부 — 엔트로피 게이트.
            # dev 는 기존 워크플로 비파괴를 위해 경고만.
            if is_production:
                raise ValueError(
                    f"SECRET_KEY is too short for AFTERGLOW_ENV=production "
                    f"(got {len(self.secret_key)} chars, require >= 32). "
                    "Generate a strong random value, e.g. `openssl rand -hex 32`."
                )
            logger.warning(
                "SECRET_KEY is shorter than 32 characters (%d). Use a strong random value "
                "(e.g. `openssl rand -hex 32`) before deploying to production.",
                len(self.secret_key),
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def load_raw_toml() -> dict:
    """afterglow.conf/config.toml 원본(+ 같은 디렉토리 오버라이드 딥 머지)을 중첩 구조 그대로 반환.

    머지 규칙: dict는 재귀 병합, 그 외는 오버라이드가 덮어쓴다. 오버라이드 파일은 알파벳순으로
    적용되어 뒤에 오는 파일이 앞의 값을 이긴다.
    """
    for path in _config_candidates():
        if path.exists() and path.stat().st_size > 0:
            with open(path, "rb") as f:
                merged = tomllib.load(f)
            for override in _config_override_paths(path):
                with open(override, "rb") as f:
                    merged = _deep_merge(merged, tomllib.load(f))
            return merged
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
