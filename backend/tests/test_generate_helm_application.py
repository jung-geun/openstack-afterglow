"""argocd/generate_helm_application.py 단위 테스트.

worker_runtime kubernetes 모드에서 매니저가 drover/notion-worker Deployment 의 replicas 를
런타임에 조정(pause=0, resume=1)한다. ArgoCD selfHeal 이 이를 git 선언값으로 되돌리지 않도록
생성되는 Application 이 해당 Deployment 의 /spec/replicas 를 ignoreDifferences 로 두는지 고정한다.
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


def test_ignore_differences_gated_off_in_static_mode():
    # 기본(static)에서는 매니저가 replicas 를 건드리지 않으므로 ArgoCD 가 계속 drift 를
    # 감지·복구하도록 무시 목록을 비워 둔다(누군가 워커를 0으로 줄이면 self-heal 로 복원).
    assert _ignore_differences_for({}, "afterglow-dev") == []
    assert _ignore_differences_for({"workerRuntime": {"mode": "static"}}, "afterglow-dev") == []
    assert _ignore_differences_for({"workerRuntime": {"mode": "docker"}}, "afterglow-dev") == []


def test_ignore_differences_enabled_only_in_kubernetes_mode():
    entries = _ignore_differences_for({"workerRuntime": {"mode": "kubernetes"}}, "afterglow")
    assert {e["name"] for e in entries} == {"drover", "notion-worker"}
    assert all(e["namespace"] == "afterglow" for e in entries)


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
