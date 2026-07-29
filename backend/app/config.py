"""Afterglow 설정 모듈.

우선순위: 환경변수 > afterglow.conf (프로젝트 루트) > 기본값
"""

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


def _config_candidates() -> list[Path]:
    """지원하는 기본 설정 파일 경로 목록."""
    return [
        Path.cwd() / "afterglow.conf",
        Path.cwd().parent / "afterglow.conf",
        Path("/app/afterglow.conf"),
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
    """같은 디렉터리의 afterglow.*.conf와 GPU 맵 오버라이드를 반환한다."""
    patterns = [f"{base_path.stem}.*{base_path.suffix}"]
    if base_path.name == "afterglow.conf":
        patterns.append("config.gpu.toml")

    overrides: dict[Path, Path] = {}
    for pattern in patterns:
        for p in base_path.parent.glob(pattern):
            if p.name == base_path.name:
                continue
            if not p.is_file() or p.stat().st_size == 0:
                continue
            overrides[p.resolve()] = p
    return [overrides[key] for key in sorted(overrides)]


def _load_toml() -> dict:
    """afterglow.conf(+ 오버라이드)을 읽어 평탄화된 dict를 반환."""
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
    flat["service_waygate_enabled"] = svc.get("waygate", False)
    flat["service_chat_enabled"] = svc.get("chat", False)
    flat["service_mcp_enabled"] = svc.get("mcp", False)
    mcp = data.get("mcp", {})
    flat["mcp_authorization_ticket_ttl_seconds"] = mcp.get("authorization_ticket_ttl_seconds", 600)
    flat["mcp_access_token_ttl_seconds"] = mcp.get("access_token_ttl_seconds", 900)
    flat["mcp_default_grant_ttl_days"] = mcp.get("default_grant_ttl_days", 30)
    flat["mcp_max_grant_ttl_days"] = mcp.get("max_grant_ttl_days", 90)
    flat["mcp_max_personal_tokens"] = mcp.get("max_personal_tokens", 10)
    flat["mcp_max_delegated_grants"] = mcp.get("max_delegated_grants", 20)
    flat["mcp_request_max_bytes"] = mcp.get("request_max_bytes", 1048576)
    flat["mcp_read_result_max_bytes"] = mcp.get("read_result_max_bytes", 524288)
    flat["mcp_mutation_result_max_bytes"] = mcp.get("mutation_result_max_bytes", 65536)
    flat["mcp_default_page_size"] = mcp.get("default_page_size", 50)
    flat["mcp_max_page_size"] = mcp.get("max_page_size", 100)
    flat["mcp_concurrent_calls_per_grant"] = mcp.get("concurrent_calls_per_grant", 4)
    flat["mcp_read_rate_per_minute"] = mcp.get("read_rate_per_minute", 120)
    flat["mcp_mutation_rate_per_minute"] = mcp.get("mutation_rate_per_minute", 20)

    k3s = data.get("k3s", {})
    flat["k3s_callback_base_url"] = k3s.get("callback_base_url", "")
    flat["k3s_kubeconfig_encryption_key"] = k3s.get("kubeconfig_encryption_key", "")
    flat["k3s_boot_volume_size_gb"] = k3s.get("boot_volume_size_gb", 30)
    flat["k3s_occm_enabled"] = k3s.get("occm_enabled", False)
    flat["k3s_occm_image"] = k3s.get(
        "occm_image",
        "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.34.1",
    )
    # Cinder CSI
    flat["k3s_cinder_csi_enabled"] = k3s.get("cinder_csi_enabled", False)
    flat["k3s_cinder_csi_image"] = k3s.get("cinder_csi_image", "registry.k8s.io/provider-os/cinder-csi-plugin:v1.34.1")
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
    # Barbican KMS
    flat["k3s_barbican_kms_enabled"] = k3s.get("barbican_kms_enabled", False)
    flat["k3s_barbican_kms_image"] = k3s.get(
        "barbican_kms_image", "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    )
    flat["k3s_barbican_kms_kek_id"] = k3s.get("barbican_kms_kek_id", "")
    # LB 네트워크 분리: OCCM Service LB 공통 VIP 서브넷
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
    flat["boot_volume_size_gb"] = nv.get("boot_volume_size_gb", 20)
    flat["upper_volume_size_gb"] = nv.get("upper_volume_size_gb", 50)

    builder = data.get("builder", {})
    flat["builder_ssh_user"] = builder.get("ssh_user", "ubuntu")
    flat["builder_ssh_key_path"] = builder.get("ssh_key_path", "/etc/afterglow/ssh/builder.key")
    flat["builder_build_timeout"] = builder.get("build_timeout", 3600)
    flat["builder_layer_share_size_gb"] = builder.get("layer_share_size_gb", 20)

    palimpsest = data.get("palimpsest", {})
    flat["palimpsest_hub_local_path"] = palimpsest.get("hub_local_path", "")
    flat["palimpsest_hub_max_blob_bytes"] = palimpsest.get("hub_max_blob_bytes", 34359738368)
    flat["palimpsest_hub_upload_ttl_seconds"] = palimpsest.get("hub_upload_ttl_seconds", 86400)
    flat["palimpsest_kvm_uri"] = palimpsest.get("kvm_uri", "")
    flat["palimpsest_kvm_layer_root"] = palimpsest.get("kvm_layer_root", "/var/lib/palimpsest/layers")
    flat["palimpsest_kvm_state_dir"] = palimpsest.get("kvm_state_dir", "/var/lib/palimpsest/domains")

    waygate = data.get("waygate", {})
    flat["waygate_callback_base_url"] = waygate.get("callback_base_url", "")
    flat["waygate_key_name"] = waygate.get("key_name", "")
    flat["waygate_default_tunnel_cidr"] = waygate.get("default_tunnel_cidr", "10.8.0.0/24")
    flat["waygate_default_listen_port"] = waygate.get("default_listen_port", 51820)

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
    # 빌트인 AI 채팅 (litellm 라우팅 + 크레딧/쿼터)
    flat["chat_default_model"] = chat.get("default_model", "")
    flat["chat_execution_protocol_version"] = chat.get("execution_protocol_version", 1)
    flat["chat_credit_per_usd"] = chat.get("credit_per_usd", 1000.0)
    flat["chat_default_monthly_quota"] = chat.get("default_monthly_quota", 100000.0)
    flat["chat_stream_enabled"] = chat.get("stream_enabled", True)
    # 외부 OpenAI/Anthropic 호환 API(/v1)를 허용할 Host 화이트리스트(콤마 구분).
    # 비면 모든 Host 허용(개발). 프로덕션은 api.cloud.dmslab.re.kr 등 전용 서브도메인만 지정 권장.
    flat["chat_api_hosts"] = chat.get("api_hosts", "")
    # "auto"는 provider/model 기본값(요청 파라미터 미주입), "none"은 명시적 비활성화다.
    # named effort는 모델 capability의 reasoning_options로 endpoint에서 검증한다.
    flat["chat_reasoning_effort"] = chat.get("reasoning_effort", "auto")
    flat["chat_mcp_oauth_callback_url"] = chat.get("mcp_oauth_callback_url", "")
    # Phase 2: LangGraph 전용 Postgres 체크포인터(비밀 — secret.yaml 주입). 미설정 시 MemorySaver fallback.
    flat["chat_checkpointer_postgres_url"] = chat.get("checkpointer_postgres_url", "")
    flat["chat_run_event_retention_hours"] = chat.get("run_event_retention_hours", 24)
    flat["chat_checkpoint_retention_days"] = chat.get("checkpoint_retention_days", 7)
    flat["chat_semantic_memory_enabled"] = chat.get("semantic_memory_enabled", False)
    flat["chat_memory_pgvector_url"] = chat.get("memory_pgvector_url", "")
    flat["chat_memory_embedding_model"] = chat.get("memory_embedding_model", "")
    flat["chat_memory_embedding_dimensions"] = chat.get("memory_embedding_dimensions", 0)
    flat["chat_memory_candidate_limit"] = chat.get("memory_candidate_limit", 20)
    flat["chat_memory_retrieval_token_budget"] = chat.get("memory_retrieval_token_budget", 1200)
    flat["chat_memory_retention_days"] = chat.get("memory_retention_days", 365)
    flat["chat_asset_s3_endpoint"] = chat.get("asset_s3_endpoint", "")
    flat["chat_asset_s3_bucket"] = chat.get("asset_s3_bucket", "")
    flat["chat_asset_s3_access_key"] = chat.get("asset_s3_access_key", "")
    flat["chat_asset_s3_secret_key"] = chat.get("asset_s3_secret_key", "")
    flat["chat_asset_s3_server_side_encryption"] = chat.get("asset_s3_server_side_encryption", "AES256")
    flat["chat_asset_s3_kms_key_id"] = chat.get("asset_s3_kms_key_id", "")
    flat["chat_asset_signed_url_ttl_seconds"] = chat.get("asset_signed_url_ttl_seconds", 300)
    flat["chat_clamav_host"] = chat.get("clamav_host", "")
    flat["chat_clamav_port"] = chat.get("clamav_port", 3310)
    flat["chat_sandbox_url"] = chat.get("sandbox_url", "")
    flat["chat_sandbox_workspace_url"] = chat.get("sandbox_workspace_url", "")
    flat["chat_sandbox_api_key"] = chat.get("sandbox_api_key", "")
    flat["chat_sandbox_image_digest"] = chat.get("sandbox_image_digest", "")
    flat["chat_sandbox_policy_version"] = chat.get("sandbox_policy_version", "")
    flat["chat_sandbox_egress_allowlist"] = chat.get("sandbox_egress_allowlist", [])

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
    mcp_authorization_ticket_ttl_seconds: int = 600
    mcp_access_token_ttl_seconds: int = 900
    mcp_default_grant_ttl_days: int = 30
    mcp_max_grant_ttl_days: int = 90
    mcp_max_personal_tokens: int = 10
    mcp_max_delegated_grants: int = 20
    mcp_request_max_bytes: int = 1048576
    mcp_read_result_max_bytes: int = 524288
    mcp_mutation_result_max_bytes: int = 65536
    mcp_default_page_size: int = 50
    mcp_max_page_size: int = 100
    mcp_concurrent_calls_per_grant: int = 4
    mcp_read_rate_per_minute: int = 120
    mcp_mutation_rate_per_minute: int = 20
    cache_ttl_operational_live: int = 30  # instances/volumes/FIP/컨테이너 상태
    cache_ttl_admin_overview: int = 60  # admin 토폴로지, 하이퍼바이저
    cache_ttl_auth_token: int = 60  # Keystone 토큰 검증 결과
    # 프로젝트별 기본 네트워크 자동 생성은 배포 운영 정책이다.
    default_network_enabled: bool = True
    default_network_cidr: str = "192.168.0.0/24"

    # 선택적 서비스
    service_magnum_enabled: bool = False
    service_manila_enabled: bool = False
    service_zun_enabled: bool = False
    service_k3s_enabled: bool = False
    service_trove_enabled: bool = False
    service_swift_enabled: bool = False
    service_barbican_enabled: bool = False
    service_waygate_enabled: bool = False  # Waygate (활성화 시 [waygate] 섹션 설정도 필요)
    service_chat_enabled: bool = False  # AI 채팅(LibreChat 임베드) (활성화 시 [chat] 섹션 설정도 필요)
    service_mcp_enabled: bool = False  # inbound consumer MCP control plane (Stage 2 rollout gate)

    # k3s 설정
    k3s_version: str = "v1.34.6+k3s1"
    k3s_callback_base_url: str = ""
    k3s_kubeconfig_encryption_key: str = ""
    k3s_boot_volume_size_gb: int = 30
    k3s_occm_enabled: bool = False
    k3s_occm_image: str = "registry.k8s.io/provider-os/openstack-cloud-controller-manager:v1.34.1"
    # Cinder CSI
    k3s_cinder_csi_enabled: bool = False
    k3s_cinder_csi_image: str = "registry.k8s.io/provider-os/cinder-csi-plugin:v1.34.1"
    # Manila CSI
    k3s_manila_csi_enabled: bool = False
    k3s_manila_csi_image: str = "registry.k8s.io/provider-os/manila-csi-plugin:v1.34.1"
    k3s_manila_csi_nfs_image: str = "registry.k8s.io/sig-storage/nfsplugin:v4.9.0"
    k3s_manila_csi_share_protocol: str = "NFS"
    # Keystone Auth
    k3s_keystone_auth_enabled: bool = False
    k3s_keystone_auth_image: str = "registry.k8s.io/provider-os/k8s-keystone-auth:v1.34.1"
    k3s_keystone_auth_policy: str = ""
    # Barbican KMS
    k3s_barbican_kms_enabled: bool = False
    k3s_barbican_kms_image: str = "registry.k8s.io/provider-os/barbican-kms-plugin:v1.34.1"
    k3s_barbican_kms_kek_id: str = ""
    # Octavia Ingress
    k3s_octavia_ingress_enabled: bool = False
    k3s_octavia_ingress_image: str = "registry.k8s.io/provider-os/octavia-ingress-controller:v1.34.1"
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

    # --- Palimpsest 허브 (레이어 레지스트리) — docs/palimpsest.md ---
    # 허브는 백엔드가 blob 을 직접 스트리밍 read/write 해야 성립하므로 Manila share 가 아니라
    # 별도 blob store 를 쓴다. 비어 있으면 허브 기능이 비활성(503)이다.
    # K8s 는 PVC, compose 는 볼륨을 이 경로에 마운트한다. 배치는 OCI image-layout 그대로:
    #   <hub_local_path>/blobs/sha256/<hex>
    palimpsest_hub_local_path: str = ""
    palimpsest_hub_max_blob_bytes: int = 34359738368  # 32 GiB — torch 급 레이어를 수용
    palimpsest_hub_upload_ttl_seconds: int = 86400  # 방치된 업로드 세션 정리 기준(초)

    # --- Palimpsest 로컬 KVM 런타임 (선택) ---
    # 비어 있으면 기능 비활성(503). `qemu:///system` 또는 `qemu+ssh://user@host/system`.
    # libvirt-python 은 별도 extra 다: `uv sync --extra kvm`
    palimpsest_kvm_uri: str = ""
    # 레이어 blob 이 놓인 호스트 경로. 허브 OCI 번들을 펼치면 이 배치가 된다:
    #   <kvm_layer_root>/blobs/sha256/<hex>
    palimpsest_kvm_layer_root: str = "/var/lib/palimpsest/layers"
    # 도메인별 루트 오버레이(qcow2)와 seed ISO 를 두는 경로
    palimpsest_kvm_state_dir: str = "/var/lib/palimpsest/domains"
    union_cephx_rotate_hours: int = 24  # CephX 키 자동 회전 주기 (0이면 비활성)
    union_auto_egress_sg_enabled: bool = True  # Union VM에 egress SG 자동 attach
    union_egress_sg_name: str = "union-egress-default"  # 자동 생성/재사용할 SG 이름

    # Waygate (WireGuard 게이트웨이)
    waygate_default_tunnel_cidr: str = "10.8.0.0/24"  # WireGuard 터널 서브넷 기본값
    waygate_default_listen_port: int = 51820  # WireGuard UDP 리슨 포트 기본값
    waygate_callback_base_url: str = ""
    waygate_key_name: str = ""

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
    # Prometheus 서버 주소. 우선순위: 환경변수 PROMETHEUS_BASE_URL > afterglow.conf [monitoring].prometheus_base_url > 기본값
    prometheus_base_url: str = "http://prometheus:9090"
    prometheus_username: str = ""  # basic auth 미사용 시 빈 문자열
    prometheus_password: str = ""

    chat_execution_protocol_version: int = 1
    # 빌트인 AI 채팅 (litellm 라우팅 + 모델별 가중 크레딧 + 월 쿼터)
    chat_default_model: str = ""  # 기본 모델명 (활성 llm_models 카탈로그의 model_name과 일치해야 함)
    chat_credit_per_usd: float = 1000.0  # 크레딧 환산율: 1 USD = N 크레딧 (예: $0.001 = 1 크레딧)
    chat_default_monthly_quota: float = 100000.0  # 신규 지갑 기본 월 쿼터(크레딧). 0 = 무제한
    chat_stream_enabled: bool = True  # SSE 스트리밍 응답 사용
    # 외부 /v1 호환 API를 허용할 Host 화이트리스트(콤마 구분). 비면 전체 허용(개발).
    chat_api_hosts: str = ""
    chat_reasoning_effort: str = (
        "auto"  # auto=provider 기본, none=명시적 비활성화, named values는 모델별 capability 검증
    )
    # Remote MCP OAuth callback URL. Empty derives the public API callback endpoint.
    chat_mcp_oauth_callback_url: str = ""
    # Phase 2: LangGraph 전용 Postgres 체크포인터 접속 URL(secret.yaml 주입). 비면 MemorySaver 사용.
    chat_checkpointer_postgres_url: str = ""
    chat_run_event_retention_hours: int = 24
    chat_checkpoint_retention_days: int = 7
    chat_semantic_memory_enabled: bool = False
    chat_memory_pgvector_url: str = ""
    chat_memory_embedding_model: str = ""
    chat_memory_embedding_dimensions: int = 0
    chat_memory_candidate_limit: int = 20
    chat_memory_retrieval_token_budget: int = 1200
    chat_memory_retention_days: int = 365
    chat_asset_s3_endpoint: str = ""
    chat_asset_s3_bucket: str = ""
    chat_asset_s3_access_key: str = ""
    chat_asset_s3_secret_key: str = ""
    chat_asset_s3_server_side_encryption: str = "AES256"
    chat_asset_s3_kms_key_id: str = ""
    chat_asset_signed_url_ttl_seconds: int = 300
    chat_clamav_host: str = ""
    chat_clamav_port: int = 3310
    chat_sandbox_workspace_url: str = ""
    chat_sandbox_url: str = ""
    chat_sandbox_api_key: str = ""
    chat_sandbox_image_digest: str = ""
    chat_sandbox_policy_version: str = ""
    chat_sandbox_egress_allowlist: list[str] = []

    # Notion 연동
    notion_config_encryption_key: str = ""  # 미설정 시 k3s_kubeconfig_encryption_key 재사용

    # GPU
    gpu_available_visible: bool = False  # true 시 사용자에게 GPU 가용량 API 노출

    # 세션 관리
    session_timeout_seconds: int = 3600
    jwt_access_ttl: int = 900  # access JWT 수명 (초), 기본 15분
    jwt_refresh_ttl: int = 604800  # refresh JWT 수명 (초), 기본 7일
    token_ip_binding_mode: str = "subnet"  # off | log | subnet | strict

    @field_validator("chat_execution_protocol_version")
    @classmethod
    def validate_chat_execution_protocol_version(cls, value: int) -> int:
        if value not in {1, 2}:
            raise ValueError("chat_execution_protocol_version must be 1 or 2")
        return value

    @field_validator("token_ip_binding_mode")
    @classmethod
    def validate_binding_mode(cls, v: str) -> str:
        _VALID_MODES = {"off", "log", "subnet", "strict"}
        if v not in _VALID_MODES:
            raise ValueError(f"token_ip_binding_mode={v!r} 은 유효하지 않습니다. 허용값: {sorted(_VALID_MODES)}")
        return v

    @field_validator("chat_mcp_oauth_callback_url")
    @classmethod
    def validate_chat_mcp_oauth_callback_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "chat.mcp_oauth_callback_url must be an absolute HTTPS URL without credentials, query, or fragment"
            )
        return value

    @model_validator(mode="after")
    def validate_semantic_memory_settings(self) -> "Settings":
        if self.chat_semantic_memory_enabled:
            if not self.chat_memory_pgvector_url:
                raise ValueError("semantic_memory_enabled requires memory_pgvector_url")
            if not self.chat_memory_embedding_model:
                raise ValueError("semantic_memory_enabled requires memory_embedding_model")
            if self.chat_memory_embedding_dimensions <= 0:
                raise ValueError("semantic_memory_enabled requires memory_embedding_dimensions > 0")
        return self

    # 보안 정책
    # True: system:all role OR admin project+role 모두 system admin 인정 (마이그레이션 호환 모드)
    # False: system:all role만 system admin으로 인정 (자기복제 권한 상승 완전 차단)
    admin_legacy_project_policy: bool = False

    # 로그인 브루트포스 방어
    login_max_attempts: int = 10  # 잠금 임계값 (실패 횟수)
    login_lockout_seconds: int = 300  # 기본 잠금 시간 (초, 5분)
    login_backoff_base: int = 2  # 지수 백오프 밑수

    # Nova 기본값
    boot_volume_size_gb: int = 20
    upper_volume_size_gb: int = 50
    builder_build_timeout: int = 3600  # 빌드 SSH 명령 최대 대기 시간 (초)
    builder_layer_share_size_gb: int = 20  # 레이어별 동적 Manila NFS share 용량 (GB)
    builder_ssh_user: str = "ubuntu"
    builder_ssh_key_path: str = "/etc/afterglow/ssh/builder.key"

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

    @property
    def chat_api_host_list(self) -> list[str]:
        """외부 /v1 API 허용 Host(소문자). 비면 [] = 전체 허용(개발)."""
        return [h.strip().lower() for h in self.chat_api_hosts.split(",") if h.strip()]

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

        # docker 모드는 백엔드 컨테이너에 /var/run/docker.sock(호스트 root 등가)을 마운트해야
        # 동작한다. 멀티테넌트 프로덕션에서 백엔드 침해 시 호스트 전체 탈취로 이어지므로,
        # 운영 부팅 시점에 fail-closed 로 거부한다. 프로덕션에서는 mode='kubernetes' 를 쓴다.
        if is_production and self.worker_runtime_mode == "docker":
            raise ValueError(
                "worker_runtime.mode='docker' mounts the host Docker socket "
                "(root-equivalent) and must NOT be used when AFTERGLOW_ENV=production. "
                "Use mode='kubernetes' for production worker management."
            )

        if self.service_mcp_enabled:
            public_api = urlsplit(self.public_api_base)
            if (
                public_api.scheme not in {"http", "https"}
                or (is_production and public_api.scheme != "https")
                or not public_api.netloc
                or public_api.username
                or public_api.password
                or public_api.query
                or public_api.fragment
            ):
                scheme_requirement = "HTTPS" if is_production else "HTTP or HTTPS"
                raise ValueError(
                    f"services.mcp requires an absolute {scheme_requirement} public_api_base without credentials, query, or fragment"
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
        mcp_positive = (
            self.mcp_authorization_ticket_ttl_seconds,
            self.mcp_access_token_ttl_seconds,
            self.mcp_default_grant_ttl_days,
            self.mcp_max_grant_ttl_days,
            self.mcp_max_personal_tokens,
            self.mcp_max_delegated_grants,
            self.mcp_request_max_bytes,
            self.mcp_read_result_max_bytes,
            self.mcp_mutation_result_max_bytes,
            self.mcp_default_page_size,
            self.mcp_max_page_size,
            self.mcp_concurrent_calls_per_grant,
            self.mcp_read_rate_per_minute,
            self.mcp_mutation_rate_per_minute,
        )
        if any(value <= 0 for value in mcp_positive):
            raise ValueError("all [mcp] limits and TTLs must be positive")
        if self.mcp_default_grant_ttl_days > self.mcp_max_grant_ttl_days:
            raise ValueError("mcp.default_grant_ttl_days may not exceed mcp.max_grant_ttl_days")
        if self.mcp_default_page_size > self.mcp_max_page_size:
            raise ValueError("mcp.default_page_size may not exceed mcp.max_page_size")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 부팅 시 실제로 읽어들인 설정 파일 목록(진단용). load_raw_toml() 첫 호출 시 채워진다.
_LOADED_CONFIG_SOURCES: list[dict] = []


def _record_source(path: Path, role: str) -> None:
    try:
        st = path.stat()
        _LOADED_CONFIG_SOURCES.append({"path": str(path), "role": role, "size": st.st_size, "mtime": st.st_mtime})
    except OSError:
        _LOADED_CONFIG_SOURCES.append({"path": str(path), "role": role, "size": None, "mtime": None})


@lru_cache
def load_raw_toml() -> dict:
    """afterglow.conf 원본(+ 같은 디렉터리 오버라이드)을 중첩 구조 그대로 반환.

    머지 규칙: dict는 재귀 병합, 그 외는 오버라이드가 덮어쓴다. 오버라이드 파일은 알파벳순으로
    적용되어 뒤에 오는 파일이 앞의 값을 이긴다.
    """
    _LOADED_CONFIG_SOURCES.clear()
    for path in _config_candidates():
        if path.exists() and path.stat().st_size > 0:
            _record_source(path, "base")
            with open(path, "rb") as f:
                merged = tomllib.load(f)
            for override in _config_override_paths(path):
                _record_source(override, "override")
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
