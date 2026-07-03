# Glance Dockerfile Layer Import

## Goal

Let admin Library Management select the actual active Ubuntu Glance image used for builder/consumer VMs and import a supported GitHub Dockerfile into a reusable squashfs layer chain/profile.

## Scope

- Persist selected Glance image fingerprints and display metadata on layer builds/artifacts.
- Resolve and validate active Ubuntu base images from Glance for new root builds and Dockerfile imports.
- Boot build and consume VMs from persisted profile base image fingerprints, with legacy fallback only for old rows.
- Add admin base-image discovery and Dockerfile import endpoints under `/api/v1/admin/libraries`.
- Parse and validate a constrained Dockerfile subset from canonical public GitHub repositories.
- Build imported Dockerfile steps into ordered sealed layer artifacts and a profile consumable by the existing layer consume path.
- Update `/admin/libraries` to use real Glance image selectors, profile image validation, and a Dockerfile import panel.
- Add focused backend/frontend regression coverage and run required gates.

## Non-goals

- No `/api/v1/admin/layers` compatibility alias.
- No private GitHub repository/token support in this change.
- No general Docker runtime compatibility for unsupported Dockerfile metadata/instructions.
- No new parallel layer consume path; completed imports use existing profiles and consume flow.
