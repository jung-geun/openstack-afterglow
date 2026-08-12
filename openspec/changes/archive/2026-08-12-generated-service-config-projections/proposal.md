# Generated service configuration projections

## Why

Kolla already generates the topology, credentials, and feature defaults required by Afterglow from `globals.yml` and `secrets.yml`, while an optional operator `afterglow.conf` carries detailed application settings. The backend correctly merges those layers, but the frontend's public configuration is currently rendered only from Kolla variables, so detailed operator branding and browser-facing integration origins do not reach the frontend.

## What Changes

- Keep `globals.yml`/`secrets.yml` as the sufficient basic configuration path for backend, frontend, and workers.
- Keep `afterglow_operator_config_source` optional for detailed application configuration without requiring operators to duplicate Kolla-owned topology or secrets.
- Build the frontend configuration by merging the generated base, optional sanitized operator layer, and final Kolla layer, then projecting a strict public allowlist.
- Mount backend/worker layers and the public frontend projection independently, preserving the secret boundary.
- Document the ownership, precedence, generated artifacts, and detailed-override workflow.

## Security

The frontend projection may contain only browser-safe fields. It must exclude credentials, database/cache URLs, secret keys, internal OpenStack authentication, encryption material, and arbitrary unknown fields even when present in the operator file.
