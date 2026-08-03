# Glance image name and tag references

## Goal

Manage Glance images with Docker-style canonical `repository:tag` names so callers can distinguish versions under one image name and names without an explicit tag resolve to `latest`.

## Contract

- The canonical reference is stored in Glance's existing `name` field as `repository:tag`; Glance's multi-valued `tags` field is not used for version identity.
- A name without a tag is normalized to `name:latest` at image creation/update boundaries and when exposing legacy names.
- A colon is treated as a tag separator only in the final path component, so registry ports remain part of the repository name.
- API responses expose the canonical full `name` plus parsed `repository` and `tag` fields. Selection continues to submit the immutable Glance image ID, allowing duplicate repositories with different tags to be selected independently.
- The image catalog mirrors Docker Hub's discovery pattern with one searchable query across repository/tag/OS, repository and tag facets, relevance/updated/name sorting, result counts, and a clear empty state.
- The VM image selector uses the same repository/tag search semantics so selecting a boot image and browsing the catalog do not disagree.
- Existing images may be renamed by operators to the canonical form; legacy names remain readable as `<name>:latest` until renamed.

## Scope

- Add shared backend parsing/normalization and response fields.
- Apply normalization to public/admin create and rename flows, image listing/detail, and image displays/selections.
- Preserve Glance tags as ordinary metadata and do not introduce a database migration.
- Add the web catalog search/filter surface and reuse its matching semantics in VM image selection.
- Add regression tests for latest defaults, explicit tags, registry ports, same-repository version selection, and repository/tag search ranking.
