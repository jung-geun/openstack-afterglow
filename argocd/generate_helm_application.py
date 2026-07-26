#!/usr/bin/env python3
"""ArgoCD Helm Application 생성기 — git path + valuesObject(env+시크릿) 주입.

배포 모델
─────────
  ArgoCD 감지 대상 (git 추적):
    helm/afterglow/values.yaml   — base 기본값
    helm/afterglow/templates/    — 차트 템플릿
    helm/afterglow/files/        — config.gpu.toml 등
    → 변경 시 ArgoCD가 자동 감지·sync

  사용자 수동 override (배포 서버 로컬, gitignore):
    helm/afterglow/values-<env>.yaml   — 환경별 config (템플릿: deploy/values-dev-example.yaml)
    helm/afterglow/secrets-<env>.yaml  — 시크릿 (템플릿: deploy/secrets-example.yaml)
    → 두 파일을 deep merge해 Application CR의 valuesObject로 주입
    → afterglow-config/afterglow-secrets 데이터는 관리자가 직접 적용할 수 있도록
      Application의 ignoreDifferences로 보호

사용법:
  # 첫 배포 또는 env config·시크릿 변경 시
  backend/.venv/bin/python argocd/generate_helm_application.py dev
  kubectl apply -f deploy/k8s/argocd-application-dev.yaml   # 시크릿 포함 — git 커밋 금지

  # afterglow.conf/Secret을 직접 바꿀 때는 generate_k8s.py 출력물을 적용한 뒤
  # 관련 Deployment를 rollout restart 한다. ArgoCD는 이 두 리소스의 data를 되돌리지 않는다.

  # 이후 values.yaml / 템플릿 변경은 git push → ArgoCD 자동 sync (재실행 불필요)

  # 또는 helm upgrade 직접 배포
  ./deploy/helm-upgrade.sh dev
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML이 필요합니다: backend/.venv/bin/python으로 실행하세요.")

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/openstack-afterglow/openstack-afterglow.git"
CHART_PATH = "helm/afterglow"

ENVS = {
    "dev": {
        "app_name": "afterglow-dev",
        "target_revision": "dev",
        "dest_namespace": "afterglow-dev",
        "image_tag": "dev",
    },
    "prod": {
        "app_name": "afterglow-prod",
        "target_revision": "main",
        "dest_namespace": "afterglow",
        "image_tag": "latest",
    },
}

IMAGES = {
    "backend": "ghcr.io/openstack-afterglow/afterglow-api",
    "frontend": "ghcr.io/openstack-afterglow/afterglow",
    "worker": "ghcr.io/openstack-afterglow/afterglow-worker",
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


# worker_runtime kubernetes 모드가 활성화되면 백엔드 매니저가 drover/notion-worker
# Deployment의 /scale 을 PATCH 한다(일시정지=replicas 0, 재개=1). 이 값은 Helm이 선언한
# replicaCount 와 달라지므로, selfHeal 이 켜진 ArgoCD가 즉시 되돌리지 않도록 무시한다.
# 이름은 backend/app/services/worker_runtime.py 의 _deployment_name 과 일치해야 한다.
_WORKER_DEPLOYMENT_NAMES = ("drover", "notion-worker")
# These resources are intentionally operator-managed.  Helm still renders them
# so they exist on a fresh install, but ArgoCD must not overwrite values that
# an administrator applies directly to the target namespace.
_ADMIN_MANAGED_RESOURCE_FIELDS = (
    ("ConfigMap", "afterglow-config", ["/data"]),
    # Helm renders stringData while the API stores Secret values in data.
    ("Secret", "afterglow-secrets", ["/data", "/stringData"]),
)


def _admin_resource_ignore_differences(namespace: str) -> list[dict]:
    return [
        {
            "group": "",
            "kind": kind,
            "name": name,
            "namespace": namespace,
            "jsonPointers": json_pointers,
        }
        for kind, name, json_pointers in _ADMIN_MANAGED_RESOURCE_FIELDS
    ]


def _worker_replica_ignore_differences(namespace: str) -> list[dict]:
    return [
        {
            "group": "apps",
            "kind": "Deployment",
            "name": name,
            "namespace": namespace,
            "jsonPointers": ["/spec/replicas"],
        }
        for name in _WORKER_DEPLOYMENT_NAMES
    ]


def _ignore_differences_for(values_object: dict, namespace: str) -> list[dict]:
    """Return resource fields that ArgoCD must leave operator-managed."""
    differences = _admin_resource_ignore_differences(namespace)
    mode = (values_object.get("workerRuntime") or {}).get("mode", "static")
    if mode == "kubernetes":
        differences.extend(_worker_replica_ignore_differences(namespace))
    return differences


def build_application(env: str) -> dict:
    cfg = ENVS[env]
    chart_dir = REPO_ROOT / CHART_PATH

    # 환경 config (배포 서버 로컬, gitignore — values.yaml 대비 override)
    values_path = chart_dir / f"values-{env}.yaml"
    if values_path.exists():
        env_values: dict = yaml.safe_load(values_path.read_text()) or {}
    else:
        print(f"경고: {values_path.name} 없음 — base values.yaml만 적용됩니다")
        print("  템플릿: deploy/values-dev-example.yaml 참조")
        env_values = {}

    # 시크릿 (배포 서버 로컬, gitignore)
    secrets_path = chart_dir / f"secrets-{env}.yaml"
    if not secrets_path.exists():
        sys.exit(
            f"시크릿 파일이 없습니다: {secrets_path}\n"
            f"  템플릿: deploy/secrets-example.yaml 참조"
        )
    secrets_doc: dict = yaml.safe_load(secrets_path.read_text()) or {}

    # env config + secrets → valuesObject (ArgoCD CR에 저장)
    values_object = _deep_merge(env_values, secrets_doc)

    tag = cfg["image_tag"]
    image_list = ",".join(f"{alias}={repo}:{tag}" for alias, repo in IMAGES.items())

    annotations = {
        "argocd-image-updater.argoproj.io/image-list": image_list,
        "argocd-image-updater.argoproj.io/write-back-method": "argocd",
    }
    for alias in IMAGES:
        annotations[f"argocd-image-updater.argoproj.io/{alias}.update-strategy"] = (
            "digest"
        )
        annotations[f"argocd-image-updater.argoproj.io/{alias}.helm.image-name"] = (
            f"image.{alias}.repository"
        )
        annotations[f"argocd-image-updater.argoproj.io/{alias}.helm.image-tag"] = (
            f"image.{alias}.tag"
        )

    spec: dict = {
        "project": "afterglow",
        "source": {
            "repoURL": REPO_URL,
            "targetRevision": cfg["target_revision"],
            "path": CHART_PATH,
            "helm": {
                # valueFiles 없음 — git의 values.yaml(base)만 자동 로드
                # env config + secrets 는 valuesObject로 ArgoCD CR에 저장
                "valuesObject": values_object,
            },
        },
        "destination": {
            "server": "https://kubernetes.default.svc",
            "namespace": cfg["dest_namespace"],
        },
    }
    ignore_differences = _ignore_differences_for(values_object, cfg["dest_namespace"])
    if ignore_differences:
        spec["ignoreDifferences"] = ignore_differences

    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": cfg["app_name"],
            "namespace": "argocd",
            "annotations": annotations,
        },
        "spec": {
            **spec,
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                },
                "syncOptions": [
                    "CreateNamespace=true",
                    "PruneLast=true",
                    "ApplyOutOfSyncOnly=true",
                    "RespectIgnoreDifferences=true",
                ],
                "retry": {
                    "limit": 3,
                    "backoff": {
                        "duration": "5s",
                        "factor": 2,
                        "maxDuration": "3m",
                    },
                },
            },
        },
    }


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ENVS:
        sys.exit(f"사용법: {sys.argv[0]} <{'|'.join(ENVS)}>")
    env = sys.argv[1]

    app = build_application(env)
    out_dir = REPO_ROOT / "deploy" / "k8s"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"argocd-application-{env}.yaml"
    header = (
        "# 이 파일은 generate_helm_application.py가 생성합니다.\n"
        "# 시크릿이 포함되어 있으므로 git에 커밋하지 마세요 (gitignore 처리됨).\n"
    )
    out_path.write_text(
        header + yaml.safe_dump(app, allow_unicode=True, sort_keys=False)
    )
    print(f"생성 완료: {out_path}")
    print(f"적용: kubectl apply -f {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
