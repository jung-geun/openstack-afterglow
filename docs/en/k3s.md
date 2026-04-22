---
title: k3s Cluster
parent: English
lang: en
nav_order: 2
---

# k3s Cluster Provisioning

**Language:** [한국어](../k3s.md) · English

Afterglow provisions Kubernetes environments by deploying k3s directly onto VMs — OpenStack's Magnum service is not required.

---

## Overview

### Advantages over Magnum

| Aspect | Magnum | Afterglow k3s |
|---|---|---|
| Install complexity | Requires Heat templates + a separate service | Runs on OpenStack core services only |
| Supported distros | Limited | Ubuntu 22.04 / 24.04 (CoreOS planned) |
| Footprint | Heavy, full Kubernetes | k3s — single binary, 512 MB memory and up |
| Provisioning speed | 10–20 min | 3–5 min |
| History | None | Soft-delete retains delete history indefinitely |

### Architecture

```
Afterglow dashboard
    │
    ├── Nova: create master-node VM
    │     └── cloud-init: install k3s server
    │
    ├── Nova: create worker-node VMs (optional)
    │     └── cloud-init: join as k3s agent
    │
    └── kubeconfig → downloaded by the user
```

---

## Creating a Cluster

### From the Dashboard

1. Go to **Containers → k3s Clusters**
2. Click **Create cluster**
3. Fill in:
   - Cluster name
   - Master-node flavor (recommended: 2 vCPU / 4 GB RAM or more)
   - Worker-node count and flavor
   - Network / security group
4. Click **Deploy** — track progress in real time

### How cloud-init Works

When creating the master-node VM, Afterglow generates the following cloud-init automatically:

```yaml
#cloud-config
package_update: true
packages:
  - curl

runcmd:
  # Install k3s server
  - curl -sfL https://get.k3s.io | sh -s - server \
      --disable traefik \
      --node-name master-01
  # Fix kubeconfig permissions
  - chmod 644 /etc/rancher/k3s/k3s.yaml
```

Worker nodes are injected with the master's join token and join the cluster automatically:

```yaml
runcmd:
  - curl -sfL https://get.k3s.io | K3S_URL=https://<master-ip>:6443 \
      K3S_TOKEN=<join-token> sh -
```

---

## Managing a Cluster

### Download kubeconfig

Cluster detail page → **Download kubeconfig** button

```bash
# Apply the downloaded kubeconfig
export KUBECONFIG=~/Downloads/afterglow-cluster.yaml
kubectl get nodes
```

### Cluster Status

| State | Meaning |
|---|---|
| `CREATING` | VM creation and k3s install in progress |
| `ACTIVE` | Running normally |
| `ERROR` | Creation failed |
| `DELETED` | Deleted (history still viewable) |

### Browsing Delete History

Deleted clusters are soft-deleted and their history is preserved:

```
Dashboard → k3s Clusters → toggle "Show deleted clusters"
```

Deleted entries are greyed out and show the deletion time and the user who deleted them.

---

## Networking

### Recommended Security-Group Rules

Inbound rules for the master node:

| Port | Protocol | Purpose |
|---|---|---|
| 6443 | TCP | Kubernetes API server |
| 10250 | TCP | kubelet API |
| 2379-2380 | TCP | etcd (multi-master) |
| 8472 | UDP | Flannel VXLAN |
| 51820 | UDP | WireGuard (optional) |

Worker nodes:

| Port | Protocol | Purpose |
|---|---|---|
| 10250 | TCP | kubelet API |
| 30000-32767 | TCP/UDP | NodePort services |
| 8472 | UDP | Flannel VXLAN |

### Attaching a Floating IP

To reach the API server from outside the cloud, attach a floating IP to the master node:

```bash
# Attach a floating IP using the OpenStack CLI
openstack floating ip create <external-network>
openstack server add floating ip <master-vm-id> <floating-ip>
```

---

## OS Support and Roadmap

### Current: Ubuntu

| Version | Status |
|---|---|
| Ubuntu 22.04 LTS (Jammy) | Supported |
| Ubuntu 24.04 LTS (Noble) | Supported |

### Planned: Fedora CoreOS

Migration to Fedora CoreOS is planned in line with immutable-infrastructure principles.

**Why CoreOS:**

- **rpm-ostree** atomic OS updates — supports rollback
- **Immutable root filesystem** — prevents drift
- **Ignition**-based declarative bootstrap (replaces cloud-init)
- Lightweight OS optimized for Kubernetes workloads

**Migration plan:**

```
Now:     Ubuntu + cloud-init
  └── k3s binary installed directly

Planned: Fedora CoreOS + Ignition
  ├── Butane YAML → Ignition JSON conversion
  ├── k3s systemd unit declared declaratively
  └── Additional packages via rpm-ostree layering
```

Example Ignition configuration (planned):

```yaml
# Butane (YAML) → Ignition (JSON) conversion
variant: fcos
version: 1.5.0
systemd:
  units:
    - name: k3s.service
      enabled: true
      contents: |
        [Unit]
        Description=k3s server
        After=network-online.target

        [Service]
        ExecStartPre=/usr/local/bin/install-k3s.sh
        ExecStart=/usr/local/bin/k3s server
        Restart=always

        [Install]
        WantedBy=multi-user.target
```

---

## Troubleshooting

### k3s Install Failed

```bash
# SSH into the VM and check cloud-init logs
sudo cat /var/log/cloud-init-output.log
sudo systemctl status k3s
```

### Worker Node Fails to Join

```bash
# On the master: check the join token
sudo cat /var/lib/rancher/k3s/server/node-token

# On the worker: check the agent
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -n 50
```

### Cannot Reach the API Server

1. Confirm port 6443 is open in the security group
2. Confirm a floating IP is attached
3. Confirm the kubeconfig's `server` field points at the floating IP:

```bash
# Update kubeconfig server address
kubectl config set-cluster default \
  --server=https://<floating-ip>:6443
```

---

## Cloud Provider OpenStack Plugins

k3s clusters integrate with various OpenStack services through the Cloud Provider OpenStack plugin registry. Each plugin can be independently enabled in the `config.toml [k3s]` section.

### Supported Plugins

| Plugin | Config Key | Purpose |
|--------|-----------|---------|
| **OCCM** (OpenStack Cloud Controller Manager) | `occm_enabled` | Node initialization, Service type LoadBalancer → automatic Octavia LB |
| **Cinder CSI** | `cinder_csi_enabled` | PVC → automatic Cinder block storage provisioning |
| **Manila CSI** | `manila_csi_enabled` | PVC → automatic Manila NFS (ReadWriteMany) provisioning |
| **Octavia Ingress** | `octavia_ingress_enabled` | Ingress resource → automatic Octavia LB creation |
| **Keystone Auth** | `keystone_auth_enabled` | Kubernetes authentication → Keystone token integration |
| **Barbican KMS** | `barbican_kms_enabled` | Kubernetes Secret at-rest encryption → Barbican integration |

### config.toml Example

```toml
[k3s]
occm_enabled = true
cinder_csi_enabled = true
manila_csi_enabled = false
octavia_ingress_enabled = false
keystone_auth_enabled = false
barbican_kms_enabled = false
```

### Plugin Deployment Process

When a cluster is created, the plugin registry aggregates:

1. **cloud.conf** — `/etc/kubernetes/cloud.conf` shared by OCCM and Cinder CSI (OpenStack credentials)
2. **manifests** — Kubernetes manifest files for each plugin
3. **server args** — K3s install arguments (e.g., `--kube-apiserver-arg`)

The cloud-init callback script deploys plugins sequentially and reports the result in the `plugin_status` field:

```json
{
  "plugin_status": {
    "occm": "deployed",
    "cinder_csi": "deployed",
    "manila_csi": "failed"
  }
}
```

A plugin that fails to deploy is marked `failed`, but the cluster itself continues to operate normally.

### Automatic Cleanup on Cluster Deletion

When a cluster with OCCM enabled is deleted, any Octavia load balancers created by Kubernetes LoadBalancer services are automatically cleaned up to prevent orphaned resources:

- All Octavia LBs matching the `kube_service_{cluster_name}_` prefix are cascade-deleted
- On cleanup failure, a warning is logged and deletion continues (best-effort)

### Node Cleanup on Scale-Down

When scaling down worker nodes, Kubernetes node objects are deleted before the VMs are removed. This prevents OCCM from entering an infinite retry loop with `failed to find object` errors.

### Checking kubeconfig Existence (HEAD)

You can use `HEAD /api/k3s/clusters/{id}/kubeconfig` to check whether a kubeconfig file exists without downloading it. This is useful for verifying cluster readiness without transferring the full file.
