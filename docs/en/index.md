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
| [Architecture](../architecture.md) _(Korean)_ | System design and data flow |
| [API reference](../api-reference.md) _(Korean)_ | Complete REST API specification |

---

## Highlights

### k3s Cluster Provisioning
Installs k3s directly onto OpenStack VMs to deliver a Kubernetes environment on demand. No complex Magnum setup — master and worker nodes are configured automatically through cloud-init.

### OverlayFS Library Layer
Mounts Manila NFS/CephFS shares as OverlayFS lower layers so that AI/ML libraries (Python, PyTorch, vLLM) can be shared across many VMs. Storage efficiency and boot speed improve at the same time.

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

[GitHub repository](https://github.com/jung-geun/openstack-afterglow){: .btn .btn-primary }
