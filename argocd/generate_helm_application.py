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

사용법:
  # 첫 배포 또는 env config·시크릿 변경 시
  backend/.venv/bin/python argocd/generate_helm_application.py dev
  kubectl apply -f deploy/k8s/argocd-application-dev.yaml   # 시크릿 포함 — git 커밋 금지

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


def build_application(env: str) -> dict:
    cfg = ENVS[env]
    chart_dir = REPO_ROOT / CHART_PATH

    # 환경 config (배포 서버 로컬, gitignore — values.yaml 대비 override)
    values_path = chart_dir / f"values-{env}.yaml"
    if values_path.exists():
        env_values: dict = yaml.safe_load(values_path.read_text()) or {}
    else:
        print(f"경고: {values_path.name} 없음 — base values.yaml만 적용됩니다")
        print(f"  템플릿: deploy/values-dev-example.yaml 참조")
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
        annotations[f"argocd-image-updater.argoproj.io/{alias}.update-strategy"] = "digest"
        annotations[f"argocd-image-updater.argoproj.io/{alias}.helm.image-name"] = (
            f"image.{alias}.repository"
        )
        annotations[f"argocd-image-updater.argoproj.io/{alias}.helm.image-tag"] = (
            f"image.{alias}.tag"
        )

    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": cfg["app_name"],
            "namespace": "argocd",
            "annotations": annotations,
        },
        "spec": {
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
    out_path.write_text(header + yaml.safe_dump(app, allow_unicode=True, sort_keys=False))
    print(f"생성 완료: {out_path}")
    print(f"적용: kubectl apply -f {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
