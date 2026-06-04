"""generate_k8s.py 단위 테스트."""

import sys
from pathlib import Path

import yaml

# generate_k8s.py is at project root, not in backend/
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from generate_k8s import render_grafana_deployment  # noqa: E402


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
