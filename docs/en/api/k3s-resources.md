---
title: k3s Resources
parent: API Reference
grand_parent: English
lang: en
nav_order: 41
---

# k3s Resource Management

This is a proxy-style API that queries/manipulates the **Kubernetes resources inside** a k3s cluster (Namespace, Pod, Deployment, ReplicaSet, Service, ConfigMap, Secret) and opens a Cloud Shell. The Afterglow backend connects to the in-cluster API server using the cluster's stored kubeconfig and acts on the user's behalf — so users can manage resources from the web without downloading the kubeconfig themselves.

For the cluster lifecycle (create/delete/scale/health/node groups/certificates), see the [k3s Cluster (k3s)](k3s.md) document.

> **Activation condition:** `afterglow.conf [services] k3s = true`

---

## Basic Information

| Item | Value |
|------|-----|
| Base path | `/api/v1/k3s/clusters` |
| Auth | All endpoints require an `Authorization: Bearer <access_token>` header (`X-Project-Id` optional) |
| Ownership verification | Every request uses `get_cluster(project_id, cluster_id)` to confirm the cluster belongs to the current project. On mismatch/nonexistence, `404` |
| Access method | In-cluster K8s API proxy via the cluster kubeconfig |
| Tags | `k3s-pods`, `k3s-workloads`, `k3s-services`, `k3s-configmaps`, `k3s-secrets`, `k3s-shell` |

> Mutations (create/update/delete/scale/restart, shell ticket) are audit-logged via `activity_recorder`. However, **Secret data is not included in the log extra** (only name/namespace are recorded).

---

## Namespace

| Method | Path | Description |
|--------|------|------|
| `GET` | `/{cluster_id}/namespaces` | Namespace list of the cluster |

---

## Pod

| Method | Path | Response | Description |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/pods` | `PodInfo[]` | Pod list in the namespace |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/pods/{name}` | `204` | Delete Pod |
| `GET` | `/{cluster_id}/namespaces/{namespace}/pods/{name}/log` | `PodLogResponse` | Get Pod logs |

**Log query parameters**

| Query | Type | Default | Description |
|------|------|------|------|
| `container` | string | — | Specify the target container in a multi-container Pod |
| `tail_lines` | int | `200` | Last N lines. Range `1–10000` |

Key `PodInfo` fields: `name`, `namespace`, `phase`, `ready`, `restarts`, `node`, `pod_ip`, `containers[]` (`name`/`image`/`ready`/`restart_count`/`state`), `labels`, `created_at`.

---

## Deployment / ReplicaSet

| Method | Path | Response | Description |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/deployments` | `DeploymentInfo[]` | Deployment list |
| `GET` | `/{cluster_id}/namespaces/{namespace}/replicasets` | `ReplicaSetInfo[]` | ReplicaSet list |
| `POST` | `/{cluster_id}/namespaces/{namespace}/deployments/{name}/restart` | `DeploymentInfo` | Rolling restart (rollout restart) |
| `PATCH` | `/{cluster_id}/namespaces/{namespace}/deployments/{name}/scale` | `DeploymentInfo` | Adjust replica count |

**scale request body** `ScaleDeploymentRequest`

```json
{ "replicas": 3 }
```

| Field | Type | Description |
|------|------|------|
| `replicas` | int | Target replica count. Range `0–100` |

Key `DeploymentInfo` fields: `name`, `namespace`, `replicas`, `available`, `ready`, `updated`, `strategy`, `selector`, `images[]`, `created_at`.

---

## Service

| Method | Path | Response | Description |
|--------|------|------|------|
| `GET` | `/{cluster_id}/namespaces/{namespace}/services` | `ServiceInfo[]` | Service list |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/services/{name}` | `204` | Delete Service |

Key `ServiceInfo` fields: `name`, `namespace`, `type`, `cluster_ip`, `external_ips[]`, `ports[]` (`port`/`target_port`/`node_port`/`protocol`), `selector`, `created_at`.

---

## ConfigMap

The list takes the namespace as a query parameter, while detail/mutation include the namespace in the path.

| Method | Path | Response | Description |
|--------|------|------|------|
| `GET` | `/{cluster_id}/configmaps?namespace={ns}` | `ConfigMapInfo[]` | ConfigMap list (default `namespace=default`) |
| `GET` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `ConfigMapInfo` | Single fetch |
| `POST` | `/{cluster_id}/namespaces/{namespace}/configmaps` | `201` `ConfigMapInfo` | Create |
| `PUT` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `ConfigMapInfo` | Update |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/configmaps/{name}` | `204` | Delete |

**Create request body** `ConfigMapCreateRequest`

| Field | Type | Description |
|------|------|------|
| `name` | string | ConfigMap name |
| `data` | object | Key-value string map |
| `labels` / `annotations` | object? | Metadata |

`PUT` takes `ConfigMapWriteRequest` (`data`, `labels`, `annotations`, `binary_data`).

---

## Secret

> **Security note**
> - `SecretInfo.data` is returned as the **base64-encoded value** exactly as in the K8s original (not plaintext-decrypted).
> - The `data` in create/update requests is received as **plaintext** and encoded by the backend.
> - Mutation audit logs record only name/namespace and **do not retain Secret values.**

| Method | Path | Response | Description |
|--------|------|------|------|
| `GET` | `/{cluster_id}/secrets?namespace={ns}` | `SecretInfo[]` | Secret list (default `namespace=default`) |
| `GET` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `SecretInfo` | Single fetch |
| `POST` | `/{cluster_id}/namespaces/{namespace}/secrets` | `201` `SecretInfo` | Create |
| `PUT` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `SecretInfo` | Update |
| `DELETE` | `/{cluster_id}/namespaces/{namespace}/secrets/{name}` | `204` | Delete |

**Create request body** `SecretCreateRequest`

| Field | Type | Default | Description |
|------|------|------|------|
| `name` | string | — | Secret name |
| `type` | string | `Opaque` | Secret type |
| `data` | object | — | Key-value (**plaintext**) |
| `labels` / `annotations` | object? | — | Metadata |

`PUT` takes `SecretWriteRequest` (`type`, `data`, `labels`, `annotations`).

---

## Cloud Shell

An exec channel that runs `kubectl`/`sh` on the cluster from a browser terminal. A short-lived ticket is issued and used for WebSocket authentication.

### `POST /{cluster_id}/shell-ticket`

Issues a one-time ticket for the WebSocket connection. If the cluster is not in the `ACTIVE` state, `409`.

**Response `201`**

```json
{ "ticket": "<url-safe-token>", "expires_in": 30 }
```

- Ticket TTL: **30 seconds** (stored in Redis, destroyed after a single use).
- Issuance is audit-logged.

### `WS /{cluster_id}/shell?ticket={ticket}`

A WebSocket endpoint that proxies the K8s exec protocol (`v4.channel.k8s.io`).

- Authenticates via the `ticket` query — if invalid, the connection is closed (`4401`); on cluster mismatch, `4403`.
- Guarantees a per-user shell Pod session, and auto-terminates on idle timeout (`4408`).
- On disconnect, the shell Pod is cleaned up on a best-effort basis.

---

## Error Codes

| Code | Description |
|------|------|
| `404` | Cluster not found (nonexistent or owned by another project) |
| `409` | (shell-ticket) Cluster is not in the `ACTIVE` state |
| `422` | Request body validation failure (e.g., `replicas` out of range) |
