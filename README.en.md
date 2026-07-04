# Afterglow

**Language:** [한국어](README.md) · English

> Next-generation OpenStack dashboard — Horizon's feature completeness combined with Skyline's modern UX

[![CI](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/test.yml/badge.svg)](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/test.yml)
[![Docker Build](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/docker-build.yml/badge.svg)](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/github/license/openstack-afterglow/openstack-afterglow)](LICENSE)

Afterglow is an open-source web dashboard for OpenStack clouds. It keeps Horizon's feature completeness and stability while delivering a modern SvelteKit UI/UX, and bundles **k3s-based Kubernetes provisioning** (a Magnum replacement) and an **OverlayFS library layer** optimized for AI/ML workloads.

## Features

- **Full OpenStack service management** — Nova · Glance · Cinder · Neutron · Manila · Octavia in a single dashboard
- **k3s cluster provisioning** — deploy k3s directly onto VMs without Magnum (OCCM · Cinder/Manila CSI · Keystone Auth · Barbican KMS plugins)
- **OverlayFS library layer (Union Mount v2)** — content-addressable immutable layers, Fork API, Manila snapshot backup/restore
- **Monitoring integration** — Grafana JWT embed, Prometheus HTTP SD, automated monitoring security groups
- **Defense-in-depth security** — IDOR guards, HKDF key-separated encryption, kubeconfig audit log, production boot guard

## Quick Start

```bash
git clone git@github.com:openstack-afterglow/openstack-afterglow.git
cd openstack-afterglow
cp afterglow.conf.example afterglow.conf   # set your OpenStack credentials
cp .env.example .env                       # local compose only: replace SECRET_KEY or keep dev-only allow flag
docker compose up -d                 # http://localhost:3000
```

`afterglow.conf` is the primary config file. Legacy `config.toml` is still read as a fallback, but new installs should use `afterglow.conf`. The `AFTERGLOW_ALLOW_INSECURE=1` flag in `.env.example` is only for local Docker Compose development; never set it in Kubernetes or production.

See the documentation below for Kubernetes / ArgoCD / kolla-ansible deployment and full configuration.

## Documentation

📖 Full docs: **<https://openstack-afterglow.github.io/openstack-afterglow/en/>**

| Document | Contents |
|---|---|
| [Getting started · Deployment](docs/en/deployment.md) | Docker Compose · Kubernetes · ArgoCD · kolla-ansible |
| [k3s cluster](docs/en/k3s.md) | k3s provisioning, node topology, CoreOS migration |
| [Architecture](docs/architecture.md) _(Korean)_ | System structure, VM-creation flow, OverlayFS |
| [API reference](docs/api-reference.md) _(Korean)_ | Complete REST API |
| [Security model](docs/security.md) _(Korean)_ | Authn/authz, IDOR guards, HKDF crypto, audit log |

Release changes: [CHANGELOG](CHANGELOG.md) · work log: [`openspec/`](openspec/) (`openspec list`, migrated from milestone.md).

## Tech Stack

| Component | Stack |
|---|---|
| Frontend | SvelteKit · TypeScript · Tailwind CSS v4 |
| Backend | FastAPI · openstacksdk (Python) |
| Cache / session | Redis 7 |
| Deployment | Docker Compose · Kubernetes (Kustomize) · ArgoCD · kolla-ansible |

## Development

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload   # backend :8000
cd frontend && npm install && npm run dev                       # frontend :3000
npm test                                                        # all tests
```

## License

MIT License — [LICENSE](LICENSE)
