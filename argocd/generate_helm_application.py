#!/usr/bin/env python3
"""ArgoCD Helm Application 생성기.

helm/afterglow/values-<env>.yaml (git 미추적, 배포 머신 전용)을 읽어
ArgoCD Application의 spec.source.helm.valuesObject로 인라인한
Application 매니페스트를 생성한다.

values 파일이 git에 없으므로 ArgoCD는 repo에서 values를 읽을 수 없다.
대신 Application CR 자체에 values를 내장하여, ArgoCD가 git의 차트 변경을
감지할 때마다 항상 이 values로 렌더링한다(기본 values로 초기화되지 않음).

사용법 (배포 머신에서):
    backend/.venv/bin/python argocd/generate_helm_application.py dev
    backend/.venv/bin/python argocd/generate_helm_application.py prod

    # 생성된 매니페스트 적용 (시크릿 포함 — git 커밋 금지, gitignore 처리됨)
    kubectl apply -f deploy/k8s/argocd-application-dev.yaml

주의:
- prod Application은 targetRevision=main 이므로 helm/afterglow 차트가
  main 브랜치에 머지된 후에만 적용할 것.
- 이미지 digest는 ArgoCD Image Updater가 spec.source.helm.parameters에
  기록(write-back-method: argocd)하므로, 이 매니페스트를 재적용하면
  parameters가 초기화되고 잠시 후 Image Updater가 다시 digest를 고정한다.
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


def build_application(env: str) -> dict:
    cfg = ENVS[env]
    values_path = REPO_ROOT / CHART_PATH / f"values-{env}.yaml"
    if not values_path.exists():
        sys.exit(f"values 파일이 없습니다: {values_path}")
    values = yaml.safe_load(values_path.read_text())

    # 레포 루트의 config.gpu.toml(배포 머신 전용 GPU 디바이스 맵 오버라이드)이 있으면
    # gpu.configToml 값으로 주입 → 차트 기본값(files/config.gpu.toml) 대신 사용된다.
    gpu_toml_path = REPO_ROOT / "config.gpu.toml"
    if gpu_toml_path.exists():
        values.setdefault("gpu", {})["configToml"] = gpu_toml_path.read_text()
        print(f"GPU 디바이스 맵 오버라이드 포함: {gpu_toml_path.name}")

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
                    "valuesObject": values,
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
