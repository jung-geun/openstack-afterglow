"""afterglow.conf compatibility tests for runtime and deployment config loading."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app import config as app_config

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config2helm  # noqa: E402
import generate_k8s  # noqa: E402


def test_config_to_helm_preserves_public_mcp_configuration():
    converted = config2helm.convert(
        {
            "services": {"mcp": True},
            "mcp": {
                "public_url": "https://mcp.example.test/control-plane/mcp",
                "oauth_consent_url": "https://app.example.test/oauth/mcp/authorize",
            },
        },
        include_secrets=False,
    )

    assert converted["services"]["mcp"] is True
    assert converted["mcp"] == {
        "publicUrl": "https://mcp.example.test/control-plane/mcp",
        "oauthConsentUrl": "https://app.example.test/oauth/mcp/authorize",
    }

    configmap = (ROOT / "helm/afterglow/templates/configmap.yaml").read_text(encoding="utf-8")
    values = (ROOT / "helm/afterglow/values.yaml").read_text(encoding="utf-8")
    assert '"mcp"' in configmap
    assert "[mcp]" in configmap
    assert "public_url = {{ .Values.mcp.publicUrl | quote }}" in configmap
    assert "oauth_consent_url = {{ .Values.mcp.oauthConsentUrl | quote }}" in configmap
    assert "mcp: false" in values
    ingress = (ROOT / "helm/afterglow/templates/ingress.yaml").read_text(encoding="utf-8")
    assert "urlParse $mcpPublicURL" in ingress
    assert "Public Streamable HTTP MCP resource and OAuth discovery endpoints." in ingress
    assert "- path: /.well-known" in ingress


@pytest.mark.parametrize(
    ("public_api_base", "expected_resource_path"),
    [
        ("https://mcp.example.test", "/api/v1/mcp"),
        ("https://mcp.example.test/gateway/", "/gateway/api/v1/mcp"),
    ],
)
def test_helm_mcp_ingress_falls_back_to_public_api_base(public_api_base, expected_resource_path):
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm is required to render the ingress contract")

    rendered = subprocess.run(
        [
            helm,
            "template",
            "afterglow",
            "helm/afterglow",
            "--show-only",
            "templates/ingress.yaml",
            "--set",
            "services.mcp=true",
            "--set",
            f"app.publicApiBase={public_api_base}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ingress = next(document for document in yaml.safe_load_all(rendered.stdout) if document["kind"] == "Ingress")
    mcp_rule = next(rule for rule in ingress["spec"]["rules"] if rule["host"] == "mcp.example.test")
    paths = {entry["path"] for entry in mcp_rule["http"]["paths"]}

    assert "mcp.example.test" in ingress["spec"]["tls"][0]["hosts"]
    assert paths == {expected_resource_path, "/.well-known"}


def test_helm_mcp_ingress_normalizes_an_explicit_origin_trailing_slash():
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm is required to render the ingress contract")

    rendered = subprocess.run(
        [
            helm,
            "template",
            "afterglow",
            "helm/afterglow",
            "--show-only",
            "templates/ingress.yaml",
            "--set",
            "services.mcp=true",
            "--set",
            "mcp.publicUrl=https://mcp.example.test/",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ingress = next(document for document in yaml.safe_load_all(rendered.stdout) if document["kind"] == "Ingress")
    mcp_rule = next(rule for rule in ingress["spec"]["rules"] if rule["host"] == "mcp.example.test")
    paths = {entry["path"] for entry in mcp_rule["http"]["paths"]}

    assert paths == {"/api/v1/mcp", "/.well-known"}


@pytest.fixture
def isolated_config_dir(tmp_path, monkeypatch):
    """Run file-discovery config tests in a temp cwd with cold config caches."""
    monkeypatch.chdir(tmp_path)
    app_config.load_raw_toml.cache_clear()
    app_config.get_settings.cache_clear()
    yield tmp_path
    app_config.load_raw_toml.cache_clear()
    app_config.get_settings.cache_clear()


def test_app_config_loads_afterglow_conf_toml_from_cwd(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[app]
site_name = "Afterglow From Conf"

[cache]
redis_url = "redis://cache.example:6379/2"
""".strip(),
        encoding="utf-8",
    )

    raw = app_config.load_raw_toml()
    flat = app_config._load_toml()

    assert raw["app"]["site_name"] == "Afterglow From Conf"
    assert raw["cache"]["redis_url"] == "redis://cache.example:6379/2"
    assert flat["site_name"] == "Afterglow From Conf"
    assert flat["redis_url"] == "redis://cache.example:6379/2"


def test_app_config_loads_login_branding_paths_from_afterglow_conf(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[app]
logo_dark_path = "/brand-dark.png"
logo_light_path = "/brand-light.png"
""".strip(),
        encoding="utf-8",
    )

    flat = app_config._load_toml()
    settings = app_config.Settings(**flat)

    assert flat["logo_dark_path"] == "/brand-dark.png"
    assert flat["logo_light_path"] == "/brand-light.png"
    assert settings.logo_dark_path == "/brand-dark.png"
    assert settings.logo_light_path == "/brand-light.png"


def test_app_config_loads_inbound_mcp_public_urls(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[mcp]
public_url = "https://mcp.example.test/control-plane/mcp"
oauth_consent_url = "https://app.example.test/oauth/mcp/authorize"
""".strip(),
        encoding="utf-8",
    )

    flat = app_config._load_toml()
    settings = app_config.Settings(**flat)

    assert settings.mcp_public_url == "https://mcp.example.test/control-plane/mcp"
    assert settings.mcp_oauth_consent_url == "https://app.example.test/oauth/mcp/authorize"


def test_app_config_applies_matching_afterglow_conf_overrides(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[app]
site_name = "Base Site"
logo_path = "/base-logo.png"

[cache]
redis_url = "redis://base-cache:6379/0"
ttl_fast = 11
""".strip(),
        encoding="utf-8",
    )
    (isolated_config_dir / "afterglow.local.conf").write_text(
        """
[app]
site_name = "Override Site"

[cache]
ttl_fast = 3
""".strip(),
        encoding="utf-8",
    )

    raw = app_config.load_raw_toml()
    flat = app_config._load_toml()

    assert raw["app"] == {
        "site_name": "Override Site",
        "logo_path": "/base-logo.png",
    }
    assert raw["cache"] == {
        "redis_url": "redis://base-cache:6379/0",
        "ttl_fast": 3,
    }
    assert flat["site_name"] == "Override Site"
    assert flat["logo_path"] == "/base-logo.png"
    assert flat["cache_ttl_fast"] == 3


def test_app_config_ignores_legacy_config_toml_files(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[app]
site_name = "Primary Site"
logo_path = "/primary-logo.png"

[cache]
redis_url = "redis://primary-cache:6379/0"
ttl_fast = 13
""".strip(),
        encoding="utf-8",
    )
    (isolated_config_dir / "config.toml").write_text(
        """
[app]
site_name = "Ignored Legacy Base"
""".strip(),
        encoding="utf-8",
    )
    (isolated_config_dir / "config.local.toml").write_text(
        """
[app]
site_name = "Ignored Legacy Override"

[cache]
ttl_fast = 4
""".strip(),
        encoding="utf-8",
    )

    raw = app_config.load_raw_toml()
    flat = app_config._load_toml()

    assert raw["app"] == {
        "site_name": "Primary Site",
        "logo_path": "/primary-logo.png",
    }
    assert raw["cache"] == {
        "redis_url": "redis://primary-cache:6379/0",
        "ttl_fast": 13,
    }
    assert flat["site_name"] == "Primary Site"
    assert flat["logo_path"] == "/primary-logo.png"
    assert flat["cache_ttl_fast"] == 13


def test_generate_k8s_main_accepts_explicit_afterglow_conf_path(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "afterglow.conf"
    config_path.write_text(
        """
[app]
site_name = "Explicit K8s Afterglow Conf"
secret_key = "0123456789abcdef0123456789abcdef"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_k8s.py",
            "--config",
            str(config_path),
            "--dry-run",
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )

    generate_k8s.main()

    output = capsys.readouterr().out
    assert "afterglow.conf" in output
    assert "afterglow-prod.conf" in output
    assert 'site_name = "Explicit K8s Afterglow Conf"' in output


def test_docker_compose_python_services_share_local_dev_secret_wiring():
    """Local compose Python services must share .env without overriding SECRET_KEY."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    expected_env_file = [{"path": ".env", "required": False}]
    for service_name in ("backend", "drover", "notion-worker", "palimpsest-worker"):
        service = services[service_name]
        assert service["env_file"] == expected_env_file
        environment = service.get("environment", {})
        names = (
            set(environment)
            if isinstance(environment, dict)
            else {str(entry).partition("=")[0] for entry in environment}
        )
        assert "SECRET_KEY" not in names


def test_env_example_allows_local_default_secret_for_compose_workers():
    """Copied .env.example must not start backend-only while workers crash."""
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "SECRET_KEY=change-me-in-production" in env_example
    assert "AFTERGLOW_ALLOW_INSECURE=1" in env_example
    assert "AFTERGLOW_ENV=development" in env_example
    assert "PUBLIC_API_BASE=http://localhost:8000" in env_example
    assert "FRONTEND_BASE_URL=http://localhost:3080" in env_example


def test_k8s_python_manifests_use_production_secret_contract():
    """K8s Python services must fail closed and share afterglow-secrets/SECRET_KEY."""
    paths = [
        ROOT / "deploy/k8s-template/base/backend/deployment.yaml",
        ROOT / "deploy/k8s-template/base/worker/deployment.yaml",
        ROOT / "deploy/k8s-template/base/worker/notion-deployment.yaml",
        ROOT / "deploy/k8s-template/base/backend/palimpsest-worker-deployment.yaml",
    ]

    for path in paths:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        env = doc["spec"]["template"]["spec"]["containers"][0]["env"]
        by_name = {item["name"]: item for item in env}

        assert by_name["AFTERGLOW_ENV"]["value"] == "production"
        assert by_name["SECRET_KEY"]["valueFrom"]["secretKeyRef"] == {
            "name": "afterglow-secrets",
            "key": "SECRET_KEY",
        }
        assert "AFTERGLOW_ALLOW_INSECURE" not in by_name


def test_helm_python_templates_use_production_secret_contract():
    """Helm Python service templates must reference the production secret contract."""
    paths = [
        ROOT / "helm/afterglow/templates/backend/deployment.yaml",
        ROOT / "helm/afterglow/templates/worker/deployment.yaml",
        ROOT / "helm/afterglow/templates/worker/notion-deployment.yaml",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")

        assert '- name: AFTERGLOW_ENV\n              value: "production"' in text
        assert "- name: SECRET_KEY" in text
        assert "name: afterglow-secrets" in text
        assert "key: SECRET_KEY" in text
        assert "AFTERGLOW_ALLOW_INSECURE" not in text


def test_app_config_loads_capability_platform_chat_settings(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[chat]
execution_protocol_version = 2
run_event_retention_hours = 48
checkpoint_retention_days = 14
semantic_memory_enabled = true
memory_pgvector_url = "postgresql://memory.example/afterglow"
memory_embedding_model = "embedding-model"
memory_embedding_dimensions = 1536
memory_candidate_limit = 12
memory_retrieval_token_budget = 900
memory_retention_days = 30
asset_s3_endpoint = "https://objects.example"
asset_s3_bucket = "chat-assets"
asset_signed_url_ttl_seconds = 120
clamav_host = "clamav"
clamav_port = 3311
sandbox_url = "https://sandbox.example"
sandbox_workspace_url = "https://workspace.example"
sandbox_image_digest = "sha256:abc"
sandbox_policy_version = "v1"
sandbox_egress_allowlist = ["api.example"]
""".strip(),
        encoding="utf-8",
    )

    settings = app_config.Settings(**app_config._load_toml())

    assert settings.chat_run_event_retention_hours == 48
    assert settings.chat_reasoning_effort == "auto"
    assert settings.chat_memory_embedding_dimensions == 1536
    assert settings.chat_asset_s3_bucket == "chat-assets"
    assert settings.chat_sandbox_egress_allowlist == ["api.example"]
    assert settings.chat_execution_protocol_version == 2
    assert settings.chat_sandbox_workspace_url == "https://workspace.example"


def test_chat_execution_protocol_version_rejects_unrecognized_version():
    with pytest.raises(ValueError):
        app_config.Settings(chat_execution_protocol_version=3)
