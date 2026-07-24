"""afterglow.conf compatibility tests for runtime and deployment config loading."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from app import config as app_config

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import generate_k8s  # noqa: E402


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


def test_app_config_applies_legacy_config_toml_overrides_to_afterglow_conf(isolated_config_dir):
    (isolated_config_dir / "afterglow.conf").write_text(
        """
[app]
site_name = "Base Legacy Site"
logo_path = "/legacy-base-logo.png"

[cache]
redis_url = "redis://legacy-base-cache:6379/0"
ttl_fast = 13
""".strip(),
        encoding="utf-8",
    )
    (isolated_config_dir / "config.local.toml").write_text(
        """
[app]
site_name = "Legacy Override Site"

[cache]
ttl_fast = 4
""".strip(),
        encoding="utf-8",
    )

    raw = app_config.load_raw_toml()
    flat = app_config._load_toml()

    assert raw["app"] == {
        "site_name": "Legacy Override Site",
        "logo_path": "/legacy-base-logo.png",
    }
    assert raw["cache"] == {
        "redis_url": "redis://legacy-base-cache:6379/0",
        "ttl_fast": 4,
    }
    assert flat["site_name"] == "Legacy Override Site"
    assert flat["logo_path"] == "/legacy-base-logo.png"
    assert flat["cache_ttl_fast"] == 4


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
    assert 'site_name = "Explicit K8s Afterglow Conf"' in output


def test_docker_compose_python_services_share_local_dev_secret_wiring():
    """Local compose Python services must share the optional .env file."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    expected_env_file = [{"path": ".env", "required": False}]
    assert services["backend"]["env_file"] == expected_env_file
    assert services["drover"]["env_file"] == expected_env_file
    assert services["notion-worker"]["env_file"] == expected_env_file

    assert "environment" not in services["backend"]
    assert "environment" not in services["drover"]
    assert "environment" not in services["notion-worker"]


def test_env_example_allows_local_default_secret_for_compose_workers():
    """Copied .env.example must not start backend-only while workers crash."""
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "SECRET_KEY=change-me-in-production" in env_example
    assert "AFTERGLOW_ALLOW_INSECURE=1" in env_example


def test_k8s_python_manifests_use_production_secret_contract():
    """K8s Python services must fail closed and share afterglow-secrets/SECRET_KEY."""
    paths = [
        ROOT / "deploy/k8s-template/base/backend/deployment.yaml",
        ROOT / "deploy/k8s-template/base/worker/deployment.yaml",
        ROOT / "deploy/k8s-template/base/worker/notion-deployment.yaml",
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
