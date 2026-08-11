# Kolla shared service connections

## Why

The four Afterglow plugin roles use Kolla variables inconsistently: application
connection strings duplicate MariaDB and Valkey construction, while Lumen's
external PostgreSQL configuration is split across host/port/user fields. This
makes a Kolla deployment harder to operate and does not provide the requested
single external PostgreSQL URL contract.

## What Changes

- Derive every plugin MariaDB endpoint and administrative connection from
  Kolla's `database_address`, `database_port`, `database_user`, and
  `database_password`; keep each application's schema/user/password separate.
- Derive every plugin Valkey endpoint from Kolla's controller API address,
  `redis_port`, and `valkey_master_password`, then reuse the resulting URL in
  templates, bootstrap jobs, APIs, and workers.
- Keep the Kolla-managed Lumen PostgreSQL container mode, and replace the
  external host/port/user/password tuple with one validated
  `lumen_external_postgres_url` used for connectivity probes and runtime.
- Render runtime OpenStack auth endpoints from Kolla's internal Keystone URL,
  region/domain values, and service-user secrets supplied through the plugin
  secrets file; provisioning continues to use Kolla's `openstack_auth`.
- Document these ownership boundaries using the stock Nova/Glance style:
  Kolla supplies control-plane topology and credentials, while the plugin
  supplies only service-scoped users, schemas, and optional external PostgreSQL
  URL.

## Constraints

- Do not alter stock Kolla playbooks, globals, passwords, or role templates.
- Do not log URLs containing passwords or render secrets into public docs.
- External PostgreSQL accepts only `postgresql://` or `postgres://` URLs and
  must be probed before Lumen starts.
- Preserve the existing bundled Lumen PostgreSQL deployment mode and all
  project-scoped Keystone provisioning behavior.
