# Repair DMSLab standalone service image deployment

## Goal
Restore the DMSLab Kolla reconfigure path for Waygate, Lumen, and Drover by replacing mutable standalone service image names with verified immutable linux/amd64 digest references in the canonical live Kolla configuration.

## Scope
- Diagnose the Waygate image-reference precheck failure on `wireguard-dmslab`.
- Resolve the published linux/amd64 manifests for the enabled Waygate, Lumen, and Drover API and worker images.
- Update only `/etc/kolla/config/afterglow/globals.yml`; preserve the canonical `globals.d` loading path and all unrelated Kolla configuration.
- Pin the bundled Lumen pgvector image to its already approved digest.
- Run the user-requested `kolla-ansible reconfigure -i multinode` and verify both controller replicas plus internal and public health routes.

## Constraints
- Do not expose or modify secrets.
- Do not change inventory, databases, service identities, or unrelated OpenStack configuration.
- Preserve source-build mode as disabled; remote service images must use `registry/repository@sha256:<64-lowercase-hex>`.
- Treat the active `dmslab-kolla-service-deployment` change as the broader deployment program; this change records only the bounded image-reference repair.

## Success criteria
- Kolla reconfigure completes with zero failed or unreachable hosts.
- Waygate, Lumen, and Drover API and worker containers run on both controllers with the configured immutable digests.
- API containers report healthy and each internal/public `/v1/health` endpoint returns `{"status":"ok"}`.
