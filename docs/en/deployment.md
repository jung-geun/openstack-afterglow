---
title: Deployment
parent: English
lang: en
nav_order: 1
---

# Deployment Guide

**Language:** [한국어](../deployment.md) · English

Afterglow supports three deployment modes: Docker Compose (development / small scale), Kubernetes (production), and ArgoCD (GitOps).

---

## Prerequisites

### OpenStack Services

| Service | Required | Purpose |
|---|---|---|
| Keystone | Required | Authentication |
| Nova | Required | VM compute |
| Glance | Required | Image management |
| Cinder | Required | Block storage |
| Neutron | Required | Networking |
| Manila | Optional | Shared filesystem (OverlayFS feature) |
| Octavia | Optional | Load balancing |

---

## Docker Compose Deployment

Suitable for development or single-host small-scale deployments.

### 1. Clone and Configure

```bash
git clone git@github.com:jung-geun/openstack-afterglow.git
cd openstack-afterglow
cp config.toml.example config.toml
```

Required `config.toml` fields:

```toml
[openstack]
auth_url             = "https://keystone.example.com:5000/v3"
project_name         = "myproject"
project_domain_name  = "Default"
user_domain_name     = "Default"
region_name          = "RegionOne"

[app]
secret_key = "your-random-secret-key-change-me"  # must be changed

[nova]
default_network_id = "your-network-uuid"
```

### 2. Start Services

```bash
# Core services (backend + frontend + redis)
docker compose up -d

# Including the monitoring stack
docker compose --profile monitoring up -d
```

### 3. Verify

```bash
# Health check
curl http://localhost:8000/api/health

# Browser
open http://localhost:3000
```

### Service Layout

| Service | Port | Description |
|---|---|---|
| frontend | 3000 | SvelteKit web UI |
| backend | 8000 | FastAPI REST API |
| redis | 6379 | Cache / session (AOF persistence) |
| opensearch | 9200 | Log search (monitoring) |
| prometheus | 9090 | Metrics collection (monitoring) |
| grafana | 3001 | Dashboards (monitoring) |

---

## Kubernetes Deployment

Production deployment. Kustomize-based `base` + `overlay` layout separates dev and prod environments.

### Prerequisites

| Item | Minimum version |
|---|---|
| kubectl | 1.28+ |
| k3s or Kubernetes | 1.28+ |
| (Optional) ArgoCD | 2.8+ |

### Directory Layout

```
deploy/k8s/
├── base/              # Shared resources
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── ingress.yaml
│   ├── cert-manager.yaml
│   ├── backend/
│   ├── frontend/
│   ├── redis/
│   ├── worker/
│   └── monitoring/
└── overlays/
    ├── dev/           # Development overlay
    └── prod/          # Production overlay
```

### 1. Create Namespace and Secrets

```bash
kubectl create namespace afterglow

kubectl create secret generic afterglow-secrets \
  --namespace=afterglow \
  --from-literal=OPENSTACK_PASSWORD=<password> \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32)
```

### 2. Kustomize Apply

```bash
# Development
kubectl apply -k deploy/k8s/overlays/dev

# Production
kubectl apply -k deploy/k8s/overlays/prod
```

### 3. Verify

```bash
kubectl get all -n afterglow
kubectl get ingress -n afterglow

# Logs
kubectl logs -f deployment/backend -n afterglow
kubectl logs -f deployment/frontend -n afterglow
```

### Key ConfigMap Settings

Edit `deploy/k8s/base/configmap.yaml`:

```yaml
data:
  OPENSTACK_AUTH_URL: "https://keystone.example.com:5000/v3"
  OPENSTACK_PROJECT_NAME: "myproject"
  OPENSTACK_REGION_NAME: "RegionOne"
  REDIS_URL: "redis://redis:6379/0"
```

### Ingress Domain

`deploy/k8s/base/ingress.yaml`:

```yaml
spec:
  rules:
    - host: afterglow.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 3000
```

> **Note**: The frontend's `PUBLIC_API_BASE` environment variable must point at an external URL reachable from the browser. Pointing it at a cluster-internal address (`http://backend:8000`) will fail because the browser cannot resolve it.

```yaml
# frontend Deployment environment
- name: PUBLIC_API_BASE
  value: "https://afterglow.example.com"
- name: ORIGIN
  value: "https://afterglow.example.com"
```

### Monitoring Stack

```bash
# Deploy the full monitoring stack
kubectl apply -f deploy/k8s/base/monitoring/

# Port-forward for local access
kubectl port-forward svc/grafana 3001:3000 -n afterglow
kubectl port-forward svc/prometheus 9090:9090 -n afterglow
```

---

## ArgoCD GitOps Deployment

Automatically syncs `dev` branch changes to the cluster.

### 1. Install ArgoCD (if not present)

```bash
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. Register Applications

```bash
kubectl apply -f argocd/appproject.yaml
kubectl apply -f argocd/application.dev.yaml    # development
kubectl apply -f argocd/application.prod.yaml   # production
```

Key fields in `argocd/application.dev.yaml`:

```yaml
spec:
  source:
    repoURL: https://github.com/jung-geun/openstack-afterglow
    targetRevision: dev          # branch to watch
    path: deploy/k8s/overlays/dev
  destination:
    server: https://kubernetes.default.svc
    namespace: afterglow-dev
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 3. Verify Sync

```bash
argocd app list
argocd app sync afterglow-dev
argocd app get afterglow-dev
```

---

## TLS / HTTPS

Use cert-manager to issue Let's Encrypt certificates automatically.

```bash
# Install cert-manager
kubectl apply -f deploy/k8s/base/cert-manager.yaml
```

Create a ClusterIssuer:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

Add TLS to the Ingress:

```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - afterglow.example.com
      secretName: afterglow-tls
```

---

## Upgrading

### Docker Compose

```bash
git pull origin dev
docker compose pull
docker compose up -d
```

### Kubernetes

```bash
# Rolling restart after image update
kubectl rollout restart deployment/backend -n afterglow
kubectl rollout restart deployment/frontend -n afterglow
kubectl rollout status deployment/backend -n afterglow
```

When using ArgoCD, pushing to the `dev` branch triggers an automatic sync.

---

## Troubleshooting

### Backend Cannot Reach OpenStack

```bash
# Check logs
docker compose logs backend
kubectl logs -f deployment/backend -n afterglow

# Test Keystone connectivity
curl -s https://keystone.example.com:5000/v3 | python3 -m json.tool
```

### Redis Connection Errors

```bash
docker compose exec backend redis-cli -u redis://redis:6379 ping
# or
kubectl exec -n afterglow deployment/backend -- redis-cli -u redis://redis:6379 ping
```

### Frontend Cannot Reach the API

1. Confirm `PUBLIC_API_BASE` resolves to a browser-reachable external URL
2. Restart the frontend after changing the domain:
   ```bash
   kubectl rollout restart deployment/frontend -n afterglow
   ```

### Pods Stuck Pending

```bash
kubectl describe pod -l app=backend -n afterglow
# Check PVC binding or resource pressure
kubectl get pvc -n afterglow
kubectl describe nodes
```
