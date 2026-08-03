# Operator-managed Kubernetes configuration

## Goal

Allow administrators to regenerate and directly apply Afterglow ConfigMap and Secret values in both `afterglow` and `afterglow-dev` without ArgoCD self-heal restoring the previous data.

## Scope

- Generate Helm Applications with ConfigMap/Secret data ignored by ArgoCD.
- Keep Helm/ArgoCD ownership for workloads and other resources.
- Add explicit dev/prod configuration profiles and safe direct-apply instructions.
- Remove the obsolete Kustomize Application manifests.
