# Proposal: Afterglow Health Checks and Lumen PostgreSQL Mode

## Why

The immutable Afterglow frontend and API images deployed to DMSLab do not include `curl`. Their Docker health checks execute `curl`, so both containers report `unhealthy` even while their HTTP endpoints return 200 through Kolla HAProxy.

Lumen currently overloads the boolean `enable_lumen_postgres` to choose between its bundled PostgreSQL container and an external database. The external path silently derives its host from the MySQL database address, which is unsafe and does not present operators with an explicit deployment choice.

## What Changes

- Replace Afterglow image-internal `curl` health checks with tools confirmed to exist in the published images: `wget` for the frontend and Python's standard library for the API.
- Validate the selected mode fail-closed before deploy or reconfigure; preserve the bundled authenticated probe and require an authenticated external `SELECT 1` before Lumen starts.
- Document both configurations in the Kolla sample globals and secrets files.

## Scope

This change only affects Afterglow container health checks and Lumen checkpointer PostgreSQL configuration. It does not change the existing DMSLab bundled PostgreSQL deployment, shared Kolla services, HAProxy routing, or PostgreSQL data.