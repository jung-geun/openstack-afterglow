# Afterglow Four-Service Kolla-Ansible Deployment Guide

This guide deploys **Afterglow**, **Drover**, **Lumen**, and **Waygate** through
the ordinary Kolla command line from `/etc/kolla`.

---

## Architecture & Integration Principles

1. **Standard Kolla Invocation**:
   - The installer appends one marker-delimited `afterglow-site.yml` import to
     Kolla's installed `site.yml`. It refuses malformed or unexpected markers.
   - It links Kolla's default `all-in-one` inventory path to `/etc/kolla/multinode`
     and also links `group_vars` and `host_vars`, preserving normal Kolla
     inventory variable discovery.
2. **Plugin-owned Variables**:
   - Settings and secrets remain in `/etc/kolla/afterglow/globals.yml` and
     `/etc/kolla/afterglow/secrets.yml`.
   - The installer links both files into Kolla's native `globals.d` loader;
     no `-e @...` arguments are required. It does not copy secret values.
   - Both files must be readable by the user that runs `kolla-ansible`; run
     the installer as that same deployment user.
3. **Kolla HAProxy Internal-VIP Listeners**:
   - HAProxy owns the internal-VIP frontend ports:
     - **Afterglow UI**: `3080`
     - **Afterglow API**: `8020`; Heat CFN retains `8000`.
     - **Waygate**: `8010`
     - **Drover**: `8011`
     - **Lumen**: `8012`
   - App containers bind the controller API addresses only, using private upstream ports `18081`, `18020`, `18010`, `18011`, and `18012`. HAProxy balances each frontend across its matching controller group.
   - A tag-selected plugin run reconciles the matching Kolla HAProxy fragments.
     Kolla recreates HAProxy only if their resulting configuration hash changes.
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

> **Prerequisite:** Complete [Configuration Setup](#configuration-setup)
> first. `install.sh` validates both plugin variable files before changing
> Kolla's installation tree.

Run `install.sh` to add the standard-command wiring:

```bash
# Auto-detect Kolla binary/directory or pass explicit paths
KOLLA_ANSIBLE_BIN=/etc/kolla/.venv/bin/kolla-ansible \
KOLLA_ANSIBLE_DIR=/etc/kolla/.venv/share/kolla-ansible \
./deploy/kolla/install.sh
```

### Installer-managed artifacts
- Role links under `$KOLLA_DIR/ansible/roles/`: `afterglow`, `drover`,
  `lumen`, and `waygate`.
- Aggregate playbook: `$KOLLA_DIR/ansible/afterglow-site.yml` ->
  `deploy/kolla/site.yml`.
- One marker-delimited `afterglow-site.yml` import in
  `$KOLLA_DIR/ansible/site.yml`.
- Default inventory link:
  `/etc/kolla/ansible/inventory/all-in-one` -> `/etc/kolla/multinode`.
- Inventory-variable directory links:
  `/etc/kolla/ansible/inventory/{group_vars,host_vars}` when their
  `/etc/kolla/{group_vars,host_vars}` sources exist.
- `globals.d` links:
  `90-openstack-afterglow-globals.yml` and
  `91-openstack-afterglow-secrets.yml`.
- An exact legacy duplicate of plugin globals is removed from stock
  `globals.yml` only after a parsed-mapping equality check; the original is
  retained as `globals.yml.before-afterglow-dedup`.

*Safety Check*: If any managed target conflicts or a `site.yml` marker is
unexpected, `install.sh` aborts rather than replacing it.

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

These two files are sufficient for a normal deployment. The role derives the
service topology and required runtime values from Kolla plus the plugin
globals/secrets, then generates and mounts the configuration needed by each
Afterglow process. A separate operator TOML is optional.


### Optional Detailed Afterglow Configuration

For settings not modeled as Kolla variables, place a partial or complete
operator TOML at `/etc/kolla/config/afterglow/afterglow.conf` on the Kolla
deployment host. The role uses this path by default. The file may contain only
the detailed keys being overridden; it does not need to repeat generated
OpenStack, database, Redis, port, URL, or service-toggle values. Keep it outside
the repository and Kolla globals files, mode `0600`:

```bash
# The Kolla deployment user must be able to read this 0600 source file.
sudo install -d -m 0700 -o "$(id -un)" -g "$(id -gn)" /etc/kolla/config/afterglow
sudo install -m 0600 -o "$(id -un)" -g "$(id -gn)" ./afterglow.conf /etc/kolla/config/afterglow/afterglow.conf
```

An optional `/etc/kolla/config/afterglow/afterglow.frontend.conf` supplies
additional browser-safe values. Both default source files are discovered by
existence; no globals override is required. Override
`afterglow_operator_config_source` or
`afterglow_operator_frontend_config_source` only when an input lives elsewhere.
Missing inputs produce empty generated layers.

The role reads the backend source only to produce a protected short-lived
staging artifact. It removes `[builder].ssh_private_key` before TOML validation.
The frontend source is projected through the same closed browser-safe allowlist
as the final frontend configuration. Raw operator files are never mounted into
containers.

Set `afterglow_ceph_monitors` in `globals.yml` from the `mon_host` value in
the deployed `/etc/kolla/config/ceph/ceph.conf`; this value is required by the
Afterglow precheck and final Kolla configuration layer.

The role writes process-specific runtime artifacts under
`/etc/kolla/config/afterglow/generated`:

1. generated `afterglow.generated.conf` base from Kolla and plugin globals/secrets;
2. sanitized `afterglow.operator.generated.conf` application override;
3. projected `afterglow.frontend.operator.generated.conf` public override;
4. generated `afterglow.zz-kolla.generated.conf` final override;
5. generated `afterglow.frontend.generated.conf`, a closed public projection of
   the merged base → backend operator → frontend operator → final result.

The backend and workers mount the generated base, sanitized backend operator,
and final override in that order. The final layer intentionally reasserts
deployment-owned OpenStack credentials/project/region/interface, database and
Redis connections, service toggles, public API/origin and CORS values,
encryption keys, Manila storage bindings, and application ports.

The frontend mounts only `afterglow.frontend.generated.conf`. Its allowlist
includes branding, refresh interval, public API/UI origins, service flags,
public S3/Grafana/chat/GitLab/MCP origins, and no credentials. Kolla-owned final
values win over both operator inputs.

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

Re-run Afterglow with the standard Kolla command after changing globals,
secrets, or the optional operator file. All generated and imported
configuration artifacts participate in the container configuration hash, so
the affected processes are recreated with the updated settings:

```bash
cd /etc/kolla
kolla-ansible reconfigure --tags afterglow
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

Never point `lumen_external_postgres_url` or `lumen_memory_pgvector_url` at
Kolla MariaDB. PostgreSQL is required for these Lumen contracts.

## Standard Inventory and Commands

Add the four plugin groups directly to `/etc/kolla/multinode`; this is the
authoritative inventory used by the ordinary Kolla command. Then run the
installer once from the plugin checkout:

```bash
KOLLA_ANSIBLE_BIN=/etc/kolla/.venv/bin/kolla-ansible \
KOLLA_ANSIBLE_DIR=/etc/kolla/.venv/share/kolla-ansible \
./deploy/kolla/install.sh
```

The installer fails rather than replacing conflicting links or unexpected
`site.yml` marker content. If it finds a legacy second YAML document in
`/etc/kolla/globals.yml`, it removes it only when its parsed mapping exactly
matches `/etc/kolla/afterglow/globals.yml`, preserving a backup beside the
stock file.

### Deploy Services

From `/etc/kolla`:

```bash
kolla-ansible deploy --tags afterglow,waygate,drover,lumen
```

### Reconfigure Services

Reconfigure only Afterglow:

```bash
kolla-ansible reconfigure --tags afterglow
```

Reconfigure all four plugin services:

```bash
kolla-ansible reconfigure --tags afterglow,waygate,drover,lumen
```

The explicit `-i`, `-p`, and `-e` form remains an escape hatch for diagnosis;
normal operations should use the commands above.

---

## Uninstallation

```bash
./deploy/kolla/uninstall.sh
```

Uninstall removes only the installer-owned `site.yml` marker block and expected
symlinks. It leaves `/etc/kolla/multinode`, plugin configuration, databases,
containers, images, and source checkouts untouched.
