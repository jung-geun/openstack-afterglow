---
layout: home
title: English
lang: en
nav_order: 99
has_children: true
permalink: /en/
---

# Afterglow

**Language:** [한국어](../) · English

> Next-generation OpenStack dashboard — Horizon's feature completeness + Skyline's modern UX

Afterglow is an open-source web dashboard for OpenStack cloud environments. It preserves Horizon's stability and feature coverage while adopting Skyline's modern UI/UX. It also ships a **k3s-based Kubernetes provisioning** stack that replaces Magnum.

---

## Quick Links

| Document | Description |
|---|---|
| [Getting started](deployment.md) | Docker Compose / Kubernetes deployment |
| [k3s cluster](k3s.md) | k3s provisioning and node management |
| [Drover behavior specification](drover-workflow.md) | Planned vs current Drover cluster creation behavior and provisioning workflow |
| [Architecture](../architecture.md) _(Korean)_ | System design and data flow |
| [API reference](../api-reference.md) _(Korean)_ | Complete REST API specification |
| [kolla-ansible deployment](../deployment.md#kolla-ansible-배포) | Single-playbook deployment inside OpenStack |

---

## Highlights

### k3s Cluster Provisioning
Installs k3s directly onto OpenStack VMs to deliver a Kubernetes environment on demand. No complex Magnum setup — master and worker nodes are configured automatically through cloud-init.

### OverlayFS Library Layer
Mounts Manila NFS/CephFS shares as OverlayFS lower layers so that AI/ML libraries (Python, PyTorch, vLLM) can be shared across many VMs. Storage efficiency and boot speed improve at the same time.

### Monitoring Integration
Issues Grafana embed JWTs (`POST /api/grafana/token`) and exposes VM targets for Prometheus via http_sd (`GET /api/sd/prometheus/targets`). Monitoring ingress security groups are attached automatically on project and instance creation.

### kolla-ansible Integration
Deploys Afterglow inside an existing OpenStack cluster using a single kolla-ansible playbook (`deploy/kolla/`).

### Complete OpenStack Service Coverage
Nova, Glance, Cinder, Neutron, Manila, Octavia — every core service managed from a single dashboard.

---

## Technology Stack

| Component | Stack |
|---|---|
| Frontend | SvelteKit + TypeScript + Tailwind CSS v4 |
| Backend | FastAPI + openstacksdk (Python) |
| Cache | Redis 7 |
| Deployment | Docker Compose / Kubernetes (Kustomize) / ArgoCD |
| CI/CD | GitHub Actions (multi-platform Docker build) |

---

[GitHub repository](https://github.com/openstack-afterglow/openstack-afterglow){: .btn .btn-primary }

---

## Release Notes

### v1.13.9 (2026-05-01)

#### New Features
- **kolla-ansible integration**: `deploy/kolla/` role and `install.sh` — single-playbook deployment inside OpenStack
- **Union Mount layer v2**: Fork API, seal/unseal, Manila Snapshot backup/restore, background build worker, volume transfer auto-detach/rollback, NFS export security hardening
- **Monitoring integration**: Grafana embed JWT, Prometheus http_sd targets, auto-attach monitoring SG
- **Octavia Ingress**: per-project manager user + App Credential auth model
- **Account settings page** (`/dashboard/account`): profile, password, theme, projects, keypairs
- Floating IP shows connected instance info
- Instance volume `delete_on_termination` toggle
- Volume snapshot per-project filtering

#### Improvements
- Sidebar redesigned — Identity & Access section, topology promoted
- API calls use `Promise.allSettled` for per-call error isolation
- ArgoCD auto-sync: kustomization digest auto-updated after image push

#### Bug Fixes
- Admin libraries ~0.5s infinite re-render loop fixed (`untrack`)
- Admin volumes action buttons condensed into `...` dropdown
- Nova error messages preserved on volume detach failure

---

### v1.13.8 and earlier

See [GitHub Releases](https://github.com/openstack-afterglow/openstack-afterglow/releases).
