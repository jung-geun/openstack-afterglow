# Afterglow Four-Service Kolla-Ansible Additive Deployment Guide

This guide describes how to deploy **Afterglow**, **Drover**, **Lumen**, and **Waygate** onto an existing Kolla-Ansible cloud as an isolated, additive plugin using native custom playbooks (`-p`).

---

## Architecture & Integration Principles

1. **Additive Kolla Integration**:
   - Stock `site.yml`, `/etc/kolla/globals.yml`, `/etc/kolla/passwords.yml`, and inventory are never modified or patched.
   - The plugin adds only its own HAProxy service fragments through Kolla's `loadbalancer-config` role. Kolla reconciles HAProxy after a fragment changes; its container may be recreated once for that deliberate route update.
2. **Custom Playbook & Additive Vars**:
   - The plugin provides an aggregate playbook `afterglow-site.yml` symlinked into Kolla's ansible directory.
   - Settings and secrets live in isolated files `/etc/kolla/afterglow/globals.yml` and `/etc/kolla/afterglow/secrets.yml`, passed via `-e @...`.
3. **Kolla HAProxy Internal-VIP Listeners**:
   - HAProxy owns the internal-VIP frontend ports:
     - **Afterglow UI**: `3080`
     - **Afterglow API**: `8020`; Heat CFN retains `8000`.
     - **Waygate**: `8010`
     - **Drover**: `8011`
     - **Lumen**: `8012`
   - App containers bind the controller API addresses only, using private upstream ports `18081`, `18020`, `18010`, `18011`, and `18012`. HAProxy balances each frontend across its matching controller group.
   - The plugin does not create external-VIP routes, DNS records, or TLS certificates. Existing Drover and Waygate public catalog URLs remain operator-owned ingress contracts.
4. **Pinned GHCR Images**:
   - DMSLab pulls published `ghcr.io/openstack-afterglow/*` images by exact linux/amd64 manifest digest. Do not use mutable `latest` or `dev` tags.
   - Source-build mode remains an optional development path; it is not used for the DMSLab deployment.
5. **Datastores & Credential Reuse**:
   - **MariaDB**: Creates plugin-owned `_kolla` schemas (`afterglow_kolla`, `drover_kolla`, `lumen_kolla`, `waygate_kolla`).
   - **Valkey (Redis)**: Connects directly to Kolla's current primary on its controller API address with explicit indexes (5: Afterglow, 6: Waygate, 7: Drover, 8: Lumen). This direct connection does not fail over automatically; update the plugin cache host after a Kolla Valkey promotion.
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
