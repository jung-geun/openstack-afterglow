"""generate_k8s.py 단위 테스트."""

import sys
from pathlib import Path

import yaml

# generate_k8s.py is at project root, not in backend/
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from generate_k8s import _render_toml_for_k8s, render_configmap, render_grafana_deployment, render_secret  # noqa: E402


def test_render_toml_includes_nova_server_image_id():
    result = _render_toml_for_k8s({"nova": {"server_image_id": "legacy-server-image"}})

    assert "[nova]" in result
    assert 'server_image_id = "legacy-server-image"' in result


def test_render_configmap_exposes_frontend_runtime_keys():
    result = render_configmap(
        {
            "cors": {"origins": "https://afterglow.example.com,http://localhost:3080"},
            "openstack": {"s3_endpoint": "https://s3.example.com"},
            "monitoring": {"grafana_base_url": "https://grafana.example.com"},
        }
    )
    doc = yaml.safe_load(result)

    assert doc["data"]["APP_ORIGIN"] == "https://afterglow.example.com"
    assert doc["data"]["PUBLIC_S3_BASE"] == "https://s3.example.com"
    assert doc["data"]["APP_GRAFANA_BASE"] == "https://grafana.example.com"
    assert "APP_S3_BASE" not in doc["data"]


def test_render_secret_rejects_default_secret_key():
    try:
        render_secret({"app": {"secret_key": "change-me-in-production"}})
    except ValueError as exc:
        assert "기본 SECRET_KEY" in str(exc)
    else:
        raise AssertionError("render_secret must reject the default SECRET_KEY")


def test_render_secret_accepts_strong_secret_key():
    result = render_secret({"app": {"secret_key": "0123456789abcdef0123456789abcdef"}})

    assert 'SECRET_KEY: "0123456789abcdef0123456789abcdef"' in result


def test_render_secret_always_emits_manifest_required_keys():
    result = render_secret({"app": {"secret_key": "0123456789abcdef0123456789abcdef"}})
    doc = yaml.safe_load(result)

    keys = doc["stringData"]
    assert keys["GITLAB_OIDC_CLIENT_SECRET"] == ""
    assert keys["K3S_KUBECONFIG_ENCRYPTION_KEY"] == ""
    assert keys["DATABASE_URL"] == ""
    assert keys["PROMETHEUS_PASSWORD"] == ""
    assert keys["BUILDER_SSH_PRIVATE_KEY"] == ""


class TestRenderGrafanaDeployment:
    def test_default_password_is_admin(self):
        result = render_grafana_deployment({})
        assert '"admin"' in result

    def test_custom_password_from_cfg(self):
        cfg = {"monitoring": {"grafana_admin_password": "s3cret"}}
        result = render_grafana_deployment(cfg)
        assert '"s3cret"' in result
        assert '"admin"' not in result

    def test_volumes_present(self):
        result = render_grafana_deployment({})
        assert "grafana-datasource" in result
        assert "grafana-dashboards-provider" in result
        assert "grafana-dashboards" in result

    def test_volume_mounts_present(self):
        result = render_grafana_deployment({})
        assert "/etc/grafana/provisioning/datasources" in result
        assert "/etc/grafana/provisioning/dashboards" in result
        assert "/var/lib/grafana/dashboards" in result

    def test_anonymous_auth_env_vars_present(self):
        result = render_grafana_deployment({})
        assert "GF_AUTH_ANONYMOUS_ENABLED" in result
        assert "GF_AUTH_ANONYMOUS_ORG_ROLE" in result
        assert "GF_SECURITY_ALLOW_EMBEDDING" in result

    def test_output_is_valid_yaml(self):
        result = render_grafana_deployment({})
        docs = list(yaml.safe_load_all(result))
        assert len(docs) >= 1
        doc = docs[0]
        assert doc["kind"] == "Deployment"
        assert doc["metadata"]["name"] == "grafana"
