# Kolla operator configuration handoff

## Why

The Kolla role renders only a deployment baseline into `afterglow.conf`; it does not carry the operator's application configuration into the containers. Operator settings such as cache policy, session controls, monitoring, chat, and branding therefore diverge from the supplied `afterglow.conf`.

## What Changes

- Accept one TOML-valid operator `afterglow.conf` source on the Kolla deployment host and copy it as an `afterglow.operator.conf` override to each Afterglow service host.
- Render a final `afterglow.zz-kolla.conf` layer that reasserts Kolla-owned topology, credentials, ports, service toggles, URLs, and storage bindings after the operator override.
- Mount the base, operator, and Kolla-final configuration layers into every Afterglow process and include all three in the container configuration hash.
- Document the staging path, file permissions, merge order, secret handling, and legacy builder-key limitation; stage the current local operator config on DMSLab.

## Constraints

- The operator config must never be committed or logged, and must be TOML-valid.
- Kolla-owned runtime values must win over the imported config.
- Do not copy legacy inline builder private keys: current Afterglow runtime intentionally ignores that unsupported field.
