"""argocd/generate_helm_application.py 단위 테스트.

ArgoCD selfHeal 이 관리자가 직접 적용한 Afterglow 설정과 충돌하지 않도록
ConfigMap/Secret 데이터 필드를 ignoreDifferences 로 생성하는지 고정한다.
worker_runtime kubernetes 모드에서는 런타임 replica 조정도 함께 보존한다.
"""

import sys
from pathlib import Path

# generate_helm_application.py 는 backend/ 가 아니라 argocd/ 에 있다.
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "argocd"))

from generate_helm_application import (  # noqa: E402
    _WORKER_DEPLOYMENT_NAMES,
    _ignore_differences_for,
    _worker_replica_ignore_differences,
)

from app.services.worker_runtime import (  # noqa: E402
    KubernetesRuntimeConfig,
    KubernetesWorkerRuntimeAdapter,
    build_worker_specs,
)


def test_worker_ignore_differences_covers_both_worker_deployments():
    entries = _worker_replica_ignore_differences("afterglow-dev")

    names = {e["name"] for e in entries}
    assert names == {"drover", "notion-worker"}
    for entry in entries:
        assert entry["group"] == "apps"
        assert entry["kind"] == "Deployment"
        assert entry["namespace"] == "afterglow-dev"
        assert entry["jsonPointers"] == ["/spec/replicas"]


def test_admin_managed_config_and_secret_data_are_always_ignored():
    entries = _ignore_differences_for({}, "afterglow-dev")

    assert {(e["kind"], e["name"]) for e in entries} == {
        ("ConfigMap", "afterglow-config"),
        ("Secret", "afterglow-secrets"),
    }
    for entry in entries:
        assert entry["group"] == ""
        assert entry["namespace"] == "afterglow-dev"
        if entry["kind"] == "ConfigMap":
            assert entry["jsonPointers"] == ["/data"]
        else:
            assert entry["jsonPointers"] == ["/data", "/stringData"]


def test_static_mode_does_not_ignore_worker_replicas():
    entries = _ignore_differences_for({"workerRuntime": {"mode": "static"}}, "afterglow-dev")

    assert all(entry["kind"] != "Deployment" for entry in entries)


def test_docker_mode_does_not_ignore_worker_replicas():
    entries = _ignore_differences_for({"workerRuntime": {"mode": "docker"}}, "afterglow-dev")

    assert all(entry["kind"] != "Deployment" for entry in entries)


def test_ignore_differences_enabled_for_worker_replicas_in_kubernetes_mode():
    entries = _ignore_differences_for({"workerRuntime": {"mode": "kubernetes"}}, "afterglow")

    assert {e["name"] for e in entries if e["kind"] == "Deployment"} == {
        "drover",
        "notion-worker",
    }
    assert all(e["namespace"] == "afterglow" for e in entries if e["kind"] == "Deployment")


def test_ignore_difference_names_match_kubernetes_adapter_deployment_names():
    # 생성기의 하드코딩 이름이 실제 어댑터가 PATCH 하는 Deployment 이름과 어긋나면
    # selfHeal 이 되돌려 pause/resume 이 깨진다. 두 소스가 일치하는지 고정한다.
    adapter = KubernetesWorkerRuntimeAdapter(
        KubernetesRuntimeConfig(
            namespace="afterglow-dev",
            service_account_token_path="/nonexistent/token",
            service_account_ca_path="/nonexistent/ca",
            manage_deployments=False,
        )
    )
    expected = {adapter._deployment_name(spec.name) for spec in build_worker_specs()}
    assert set(_WORKER_DEPLOYMENT_NAMES) == expected
