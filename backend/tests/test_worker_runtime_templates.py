"""Worker runtime deployment template regression tests."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

_WORKER_RUNTIME_LABEL = "afterglow.worker-runtime"
_RBAC_KINDS = {"ServiceAccount", "Role", "RoleBinding"}


def _render_helm_template(*args: str) -> list[dict]:
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm not available locally")

    command = [
        helm,
        "template",
        "afterglow",
        str(ROOT / "helm/afterglow"),
        "--namespace",
        "afterglow",
        *args,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr or result.stdout
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _render_worker_runtime_overlay() -> list[dict]:
    kubectl = shutil.which("kubectl")
    if kubectl is None:
        pytest.skip("kubectl not available locally")

    command = [kubectl, "kustomize", str(ROOT / "deploy/k8s-template/overlays/worker-runtime")]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        output = f"{result.stdout}\n{result.stderr}".lower()
        if 'unknown command "kustomize"' in output or "invalid subcommand" in output:
            pytest.skip("kubectl kustomize is not supported by this kubectl build")
        raise AssertionError(result.stderr or result.stdout)
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def _find_doc(docs: list[dict], kind: str, name: str) -> dict:
    for doc in docs:
        metadata = doc.get("metadata", {})
        if doc.get("kind") == kind and metadata.get("name") == name:
            return doc
    raise AssertionError(f"missing {kind} {name}")


def _worker_runtime_rbac_docs(
    docs: list[dict], service_account_name: str = "afterglow-backend-worker-runtime"
) -> list[dict]:
    expected_names = {
        service_account_name,
        f"{service_account_name}-role",
        f"{service_account_name}-binding",
    }
    matched = []
    for doc in docs:
        if doc.get("kind") not in _RBAC_KINDS:
            continue
        metadata = doc.get("metadata", {})
        labels = metadata.get("labels", {})
        if labels.get(_WORKER_RUNTIME_LABEL) == "true" or metadata.get("name") in expected_names:
            matched.append(doc)
    return matched


def _rule_for(role: dict, resources: list[str]) -> dict:
    for rule in role["rules"]:
        if rule.get("resources") == resources:
            return rule
    raise AssertionError(f"missing rule for {resources}")


def _assert_minimal_worker_rbac(role: dict) -> None:
    """최소권한 확인: deployment 조회 + /scale patch 만, 전체 deployment patch/update·pods 권한 없음.

    SA 토큰 유출 시 image/command 등 deployment 스펙 변경이나 pods 열람을 막기 위함.
    """
    assert _rule_for(role, ["deployments"])["verbs"] == ["get"]
    assert _rule_for(role, ["deployments/scale"])["verbs"] == ["patch"]
    all_resources = [rule.get("resources") for rule in role["rules"]]
    assert ["pods"] not in all_resources, "pods 권한은 어댑터 미사용 — 부여 금지"


def test_helm_static_render_has_no_worker_runtime_rbac_or_service_account_name():
    docs = _render_helm_template()

    backend = _find_doc(docs, "Deployment", "backend")

    assert "serviceAccountName" not in backend["spec"]["template"]["spec"]
    assert _worker_runtime_rbac_docs(docs) == []


def test_helm_kubernetes_mode_without_rbac_keeps_only_backend_service_account_name():
    docs = _render_helm_template(
        "--set",
        "workerRuntime.mode=kubernetes",
        "--set-string",
        "workerRuntime.kubernetes.serviceAccountName=custom-worker-runtime",
        "--set",
        "workerRuntime.kubernetes.rbac.create=false",
    )

    backend = _find_doc(docs, "Deployment", "backend")

    assert backend["spec"]["template"]["spec"]["serviceAccountName"] == "custom-worker-runtime"
    assert _worker_runtime_rbac_docs(docs, "custom-worker-runtime") == []


def test_helm_kubernetes_mode_with_rbac_renders_worker_runtime_permissions():
    docs = _render_helm_template(
        "--set",
        "workerRuntime.mode=kubernetes",
        "--set-string",
        "workerRuntime.kubernetes.serviceAccountName=custom-worker-runtime",
        "--set",
        "workerRuntime.kubernetes.rbac.create=true",
    )

    backend = _find_doc(docs, "Deployment", "backend")
    service_account = _find_doc(docs, "ServiceAccount", "custom-worker-runtime")
    role = _find_doc(docs, "Role", "custom-worker-runtime-role")
    role_binding = _find_doc(docs, "RoleBinding", "custom-worker-runtime-binding")

    assert backend["spec"]["template"]["spec"]["serviceAccountName"] == "custom-worker-runtime"
    assert service_account["metadata"]["labels"][_WORKER_RUNTIME_LABEL] == "true"
    _assert_minimal_worker_rbac(role)
    assert role_binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "custom-worker-runtime",
            "namespace": "afterglow",
        }
    ]
    assert role_binding["roleRef"] == {
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "Role",
        "name": "custom-worker-runtime-role",
    }


def test_worker_runtime_kustomize_overlay_renders_rbac_and_backend_service_account_name():
    docs = _render_worker_runtime_overlay()

    backend = _find_doc(docs, "Deployment", "backend")
    service_account = _find_doc(docs, "ServiceAccount", "afterglow-backend-worker-runtime")
    role = _find_doc(docs, "Role", "afterglow-backend-worker-runtime-role")
    role_binding = _find_doc(docs, "RoleBinding", "afterglow-backend-worker-runtime-binding")

    assert backend["spec"]["template"]["spec"]["serviceAccountName"] == "afterglow-backend-worker-runtime"
    assert service_account["metadata"]["labels"][_WORKER_RUNTIME_LABEL] == "true"
    _assert_minimal_worker_rbac(role)
    assert role_binding["subjects"] == [
        {
            "kind": "ServiceAccount",
            "name": "afterglow-backend-worker-runtime",
            "namespace": "afterglow",
        }
    ]
    assert role_binding["roleRef"] == {
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "Role",
        "name": "afterglow-backend-worker-runtime-role",
    }
