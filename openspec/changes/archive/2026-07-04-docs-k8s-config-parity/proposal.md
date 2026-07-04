# docs-k8s-config-parity

## Why
The repository now treats `afterglow.conf` as the preferred runtime configuration file while preserving `config.toml` compatibility. Kubernetes and Helm manifests also require production-mode Python services to share `/app/afterglow.conf` and `afterglow-secrets`; stale docs still referenced old paths and omitted required Secret keys.

## What Changes
- Root quickstart docs explain `afterglow.conf`, `.env.example`, and local-only `AFTERGLOW_ALLOW_INSECURE=1`.
- Korean and English deployment guides document Docker Compose `.env`, production-only root-level K8s `configmap.yaml`/`secret.yaml`, required Secret keys, generator validation, Helm Secret ownership, ArgoCD manifest paths, and restart commands.
- Static Kubernetes README documents the actual `deploy/k8s-template/` layout, worker parity, production guardrails, deployable Secret commands, and the `overlays/dev` namespace caveat.
- Generator and K8s template support the documented static manifest contract by ensuring non-optional Secret keys exist.

## Non-goals
- No API contract changes.
- No new deployment mechanism.
- No migration away from legacy `config.toml` fallback; existing compatibility remains documented where relevant.

## Success criteria
- Documentation names `afterglow.conf` as the preferred config file and `config.toml` as legacy fallback.
- K8s/Helm docs state that backend, drover, and notion-worker all mount `/app/afterglow.conf`, read `afterglow-secrets/SECRET_KEY`, and run with `AFTERGLOW_ENV=production`.
- Docs state that `AFTERGLOW_ALLOW_INSECURE=1` is local-dev only and forbidden in production/Kubernetes.
- Render/generator docs include required static-manifest Secret keys: `OS_PASSWORD`, `SECRET_KEY`, `GITLAB_OIDC_CLIENT_SECRET`, `K3S_KUBECONFIG_ENCRYPTION_KEY`, `DATABASE_URL`, `PROMETHEUS_PASSWORD`, and `BUILDER_SSH_PRIVATE_KEY`.
- Docs do not present the root `configmap.yaml`/`secret.yaml` sequence as a deployable dev path; dev/ArgoCD users must create `afterglow-config` and `afterglow-secrets` in the destination namespace or supply them through ExternalSecret.
