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
   - **Lumen PostgreSQL**: Set `lumen_postgres_mode: bundled` to create the plugin-owned `lumen_postgres` container (`pgvector/pgvector:0.8.6-pg16@sha256:a3625087...`) on the first Lumen controller, or `external` to connect to an explicitly configured operator-managed PostgreSQL endpoint. External mode does not create a persistent PostgreSQL server container; it starts a disposable verification client container, runs an authenticated `SELECT 1`, then removes it.

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


### Afterglow Operator Configuration Handoff

Place the operator source at
`/etc/kolla/config/afterglow/afterglow.conf` on the Kolla deployment host.
Keep it outside the repository and Kolla globals files, mode `0600`:

```bash
# The Kolla deployment user must be able to read this 0600 source file.
sudo install -d -m 0700 -o "$(id -un)" -g "$(id -gn)" /etc/kolla/config/afterglow
sudo install -m 0600 -o "$(id -un)" -g "$(id -gn)" ./afterglow.conf /etc/kolla/config/afterglow/afterglow.conf
```

```yaml
# /etc/kolla/afterglow/globals.yml
afterglow_operator_config_source: "/etc/kolla/config/afterglow/afterglow.conf"
```

The role reads this file only to produce a protected short-lived staging
artifact. It removes `[builder].ssh_private_key` before TOML validation and
copies only the sanitized artifact into the Afterglow configuration directory;
the raw file is never mounted into a container.

Set `afterglow_ceph_monitors` in `globals.yml` from the `mon_host` value in
the deployed `/etc/kolla/config/ceph/ceph.conf`; this value is required by the
Afterglow precheck and final Kolla configuration layer.

It then mounts three TOML layers into the backend and workers, in this order:

1. generated `afterglow.conf` base;
2. operator-managed `afterglow.operator.conf`;
3. generated `afterglow.zz-kolla.conf` final override.

The final layer intentionally reasserts deployment-owned OpenStack
credentials/project/region/interface, database and Redis connections,
service toggles, public API/origin and CORS values, encryption keys, Manila
storage bindings, and application ports. The operator layer owns
application-level configuration such as branding, cache/session policy,
monitoring, chat, SMTP, GitLab OIDC non-secret settings, and GPU settings.

### Kolla Shared Connection Inputs

Do not duplicate Kolla control-plane topology or administrative credentials in
the plugin files. Each service derives its MariaDB host, port, administrative
user, and administrative password from Kolla's `database_address`,
`database_port`, `database_user`, and `database_password`. The plugin secrets
file contains only each service's own schema-user password.

Likewise, each service derives its Redis/Valkey endpoint from the first
Kolla Valkey controller API address, `redis_port`, and
`valkey_master_password`; `*_redis_db_index` is the only cache connection
setting in `globals.yml`. This matches the topology used by Kolla's services
and keeps the password in Kolla's existing password file.

Runtime OpenStack settings use Kolla's `keystone_internal_url`, project/user
domain, region, and internal interface variables. Kolla's `openstack_auth`
provisions service projects/users; the matching runtime service-user passwords
remain in `/etc/kolla/afterglow/secrets.yml`. This follows the internal
Keystone configuration pattern used by Nova and Glance.
Secrets remain in `/etc/kolla/afterglow/secrets.yml`; do not put them in
`globals.yml` or commit the operator file.

`[builder].ssh_private_key` in legacy configuration files is not a supported
runtime setting and is deliberately not transferred. Provision a builder key
only through a future declared secret mount that is consumed by the runtime.
`config.gpu.toml` is also not copied independently; place its supported
settings in the operator TOML file until that file has an explicit handoff.

Re-run the scoped Kolla deployment after changing the operator file. Its
checksum is included in the container configuration hash, so the backend and
workers are recreated with the updated settings:

```bash
PATH=/etc/kolla/.venv/bin:$PATH \
/etc/kolla/.venv/bin/kolla-ansible reconfigure \
  -i /etc/kolla/inventory-afterglow \
  -p /etc/kolla/.venv/share/kolla-ansible/ansible/afterglow-site.yml \
  -e @/etc/kolla/afterglow/globals.yml \
  -e @/etc/kolla/afterglow/secrets.yml \
  --tags afterglow
```

### Afterglow Public Frontend Endpoint

Set `afterglow_public_endpoint_url` to the browser-facing HTTP(S) origin without a path. The role renders it into the frontend `ORIGIN`, backend CORS origin, frontend base URL, OAuth callback, and instance-health callback base. The DMSLab configuration uses `https://cloud.dmslab.re.kr`.

`afterglow_public_api_base` is the browser API origin. DMSLab's ingress routes `https://cloud.dmslab.re.kr/api/v1` to the backend, so it uses the same HTTPS origin and avoids mixed-content requests.

### Kolla External HAProxy Route

Set `afterglow_public_haproxy_enabled: true` and
`afterglow_public_haproxy_fqdn` to publish the configured hostname through
Kolla's existing external VIP/TLS frontend. The plugin owns the added HAProxy
fragment and map entry: `/api/` is dispatched to the Afterglow API backend and
all other paths to the frontend backend. It neither patches stock Kolla
templates nor changes Kolla's certificate, DNS, external VIP, or global config.

The Kolla external TLS certificate must cover the configured hostname.

### Drover, Waygate, and Lumen Public HAProxy Routes

Each service's `<service>-api` HAProxy entry stays internal (bound to the
internal VIP), so `<service>_internal_endpoint_url`/`<service>_admin_endpoint_url`
keep working unchanged. Set `drover_public_haproxy_enabled: true` /
`waygate_public_haproxy_enabled: true` / `lumen_public_haproxy_enabled: true`
with the matching `*_public_haproxy_fqdn` to add a second `<service>-public`
HAProxy entry that publishes the API directly on Kolla's external VIP/TLS
frontend (no loopback router is needed since each service exposes a single
API path). Disabling the toggle removes the plugin-owned `.cfg` fragment and
external-frontend-map entry on the next `reconfigure`. The Kolla external TLS
certificate must cover each enabled hostname.

### Lumen PostgreSQL Mode

`lumen_postgres_mode` is an explicit mutually exclusive choice for Lumen's LangGraph checkpointer:

- `bundled`: this Kolla plugin role runs its isolated `lumen_postgres`
  container on the first Lumen controller and verifies an authenticated
  `SELECT 1`. Kolla 2025.2 has no stock PostgreSQL role.
- `external`: set `lumen_external_postgres_url` in
  `/etc/kolla/afterglow/secrets.yml` to one `postgresql://` (or `postgres://`)
  URL. The role creates no PostgreSQL resource, validates the URL, writes a
  temporary mode-0600 libpq service file, runs an authenticated `SELECT 1`,
  then deletes that file. The URL never appears in the `psql` command line.

`lumen_memory_pgvector_url` is a separate optional PostgreSQL URL for semantic
memory. It is required only when `lumen_enable_pgvector: true`; provide it in
the same secret file rather than splitting it into host, port, and password
variables.

Do not configure an external Lumen PostgreSQL URL with the Kolla MariaDB
endpoint. Select one mode and set only that mode's secret input.

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
