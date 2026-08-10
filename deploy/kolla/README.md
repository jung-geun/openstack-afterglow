# Afterglow Four-Service Kolla-Ansible Additive Deployment Guide

This guide describes how to deploy **Afterglow**, **Drover**, **Lumen**, and **Waygate** onto an existing Kolla-Ansible cloud as an isolated, additive plugin using native custom playbooks (`-p`).

---

## Architecture & Integration Principles

1. **Zero Impact on Stock Kolla Configuration**:
   - Stock `site.yml`, `/etc/kolla/globals.yml`, `/etc/kolla/passwords.yml`, and HAProxy configuration files are **never modified or patched**.
   - No stock Kolla containers are restarted or altered.
2. **Custom Playbook & Additive Vars**:
   - The plugin provides an aggregate playbook `afterglow-site.yml` symlinked into Kolla's ansible directory.
   - Settings and secrets live in isolated files `/etc/kolla/afterglow/globals.yml` and `/etc/kolla/afterglow/secrets.yml`, passed via `-e @...`.
3. **Direct Internal-VIP Listeners**:
   - Services bind directly to `kolla_internal_vip_address` (e.g. `172.30.0.253`):
     - **Afterglow UI**: `3080`
     - **Afterglow API**: `8000`
     - **Waygate**: `8010`
     - **Drover**: `8011`
     - **Lumen**: `8012`
   - Nonlocal binding (`net.ipv4.ip_nonlocal_bind=1`) allows active/standby controllers to share port definitions without HAProxy reloads.
4. **Pinned Source Builds**:
   - Images are built on controller hosts from pinned GitHub source commits into local tags (`afterglow-local/<component>:<12-char-sha>`):
     - **Afterglow**: `openstack-afterglow/openstack-afterglow` (`backend`, `frontend`)
     - **Drover**: `openstack-afterglow/drover` at `2b82bc16fc432ce84b21390a67106f3afcc593a1` (`drover-api`, `drover-worker`)
     - **Lumen**: `openstack-afterglow/lumen` at `c7d59a255148173232e5a4b32e90498dea5cee29` (`lumen-api`, `lumen-worker`)
     - **Waygate**: `openstack-afterglow/waygate` at `e83ce559e3e3b08a4f28d7a46818b6c69b6c4cf3` (`waygate-api`, `waygate-worker`)
5. **Datastores & Credential Reuse**:
   - **MariaDB**: Creates plugin-owned `_kolla` schemas (`afterglow_kolla`, `drover_kolla`, `lumen_kolla`, `waygate_kolla`).
   - **Valkey (Redis)**: Reuses Kolla's Valkey master with explicit indexes (5: Afterglow, 6: Waygate, 7: Drover, 8: Lumen).
   - **Managed PostgreSQL**: Starts a single `lumen_postgres` container (`pgvector/pgvector:0.8.6-pg16@sha256:a3625087...`) on `dms-controller1` for LangGraph checkpointer storage.

---

## Installation & Symlink Creation

Run `install.sh` to create non-conflicting symlinks in Kolla's installation path:

```bash
# Auto-detect Kolla binary/directory or pass explicit paths
KOLLA_ANSIBLE_BIN=/etc/kolla/.venv/bin/kolla-ansible \
KOLLA_ANSIBLE_DIR=/etc/kolla/.venv/share/kolla-ansible \
./deploy/kolla/install.sh
```

### Created Symlinks
- Roles under `$KOLLA_DIR/ansible/roles/`: `afterglow`, `drover`, `lumen`, `waygate`
- Aggregate Playbook under `$KOLLA_DIR/ansible/`: `afterglow-site.yml` -> `deploy/kolla/site.yml`

*Safety Check*: If any target path exists and is not an exact expected symlink, `install.sh` aborts without mutating files.

---

## Configuration Setup

1. **Create Additive Directory**:
   ```bash
   sudo mkdir -p /etc/kolla/afterglow
   ```
2. **Create Globals (`/etc/kolla/afterglow/globals.yml`)**:
   Copy and customize `deploy/kolla/globals.afterglow.sample.yml`.
3. **Create Secrets (`/etc/kolla/afterglow/secrets.yml`)**:
   Copy `deploy/kolla/passwords.afterglow.additions.yml`, set permissions to `0600`, and populate generated 64-hex keys and database/Keystone passwords.

---

## Inventory Directory Overlay

Create an inventory overlay directory (e.g. `/etc/kolla/inventory-afterglow`):
```bash
mkdir -p /etc/kolla/inventory-afterglow
ln -s /etc/kolla/multinode /etc/kolla/inventory-afterglow/00-kolla
```
Place a `10-afterglow` file containing the service target nodes (e.g. `[afterglow]`, `[drover]`, `[lumen]`, `[waygate]` on control nodes).

---

## Deployment & Reconfiguration Commands

### Deploy Services
```bash
PATH=/etc/kolla/.venv/bin:$PATH \
/etc/kolla/.venv/bin/kolla-ansible deploy \
  -i /etc/kolla/inventory-afterglow \
  -p /etc/kolla/.venv/share/kolla-ansible/ansible/afterglow-site.yml \
  -e @/etc/kolla/afterglow/globals.yml \
  -e @/etc/kolla/afterglow/secrets.yml \
  --tags afterglow,waygate,drover,lumen
```

### Reconfigure Services
```bash
PATH=/etc/kolla/.venv/bin:$PATH \
/etc/kolla/.venv/bin/kolla-ansible reconfigure \
  -i /etc/kolla/inventory-afterglow \
  -p /etc/kolla/.venv/share/kolla-ansible/ansible/afterglow-site.yml \
  -e @/etc/kolla/afterglow/globals.yml \
  -e @/etc/kolla/afterglow/secrets.yml \
  --tags afterglow,waygate,drover,lumen
```

---

## Uninstallation

To cleanly remove the plugin symlinks without touching stock Kolla files or plugin containers/data:

```bash
./deploy/kolla/uninstall.sh
```

Uninstaller verifies that each destination is a symlink pointing to expected plugin targets before removal.
