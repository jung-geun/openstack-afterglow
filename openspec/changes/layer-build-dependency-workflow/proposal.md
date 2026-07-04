# layer-build-dependency-workflow

## Goal

Enforce the dependency-ordered admin layer build workflow: root tool/system/template layers (`uv` curl-installed tool layer, apt-installable `system` package layer, or curated `nvidia` driver template layer) plus `uv` → Python runtime layer → pip package layer for Python stacks.

## Scope

- Backend build request validation rejects unsupported layer kinds and invalid field combinations.
- Backend supports apt-installable system package root layers as `kind="system"` with explicit `apt_packages` metadata.
- Backend supports a curated NVIDIA compute driver root template as `kind="nvidia"` with an explicit driver branch and generated package metadata.
- Backend parent contract validation enforces direct `uv` parents for Python runtime layers and Python lineage for pip package layers; `system` and `nvidia` artifacts do not satisfy the Python runtime parent contract.
- Backend recipe orchestration splits system apt package capture, NVIDIA repository/template capture, Python runtime installation, and pip package installation.
- Admin layer UI presents a System/tool card with an uv preset, apt package build path, and NVIDIA driver template path, plus separate forms for Python runtime layers and Python package layers.
- Regression tests cover pinned pip specs such as `numpy==1.26.4`, invalid legacy Python+pip combinations, apt package validation, and NVIDIA template validation.


### Ubuntu base selector extension

- Admin root layer builds (`uv`, `system`, and `nvidia`) accept a normalized Ubuntu base key: `ubuntu-18.04`, `ubuntu-20.04`, `ubuntu-22.04`, or `ubuntu-24.04`.
- Backend resolves that logical Ubuntu base to a canonical OpenStack image ID and uses the same image mapping for layer builder VMs and default layer consumer VMs.
- Python runtime and pip package child layers inherit the normalized Ubuntu base from their selected parent lineage; explicit mismatches are rejected before build side effects.
- Profiles and consume requests reject mixed Ubuntu base stacks before creating ports, share access rules, or servers.
- Existing legacy `ubuntu-24.04-server-2026-04-15` metadata remains compatible through normalization and is displayed as `ubuntu-24.04`.
## Non-goals

- No mutation or backfill of existing artifacts built before this workflow split.
- No expansion to full PEP 508 package spec parsing; only the existing safe whitelist is supported.
- No Dockerfile parsing, Dockerfile upload/input fields, raw shell snippets, arbitrary curl URLs, or user-supplied installer scripts; NVIDIA support is a fixed server-side template only.

## Acceptance

- New `uv`, `system`, `nvidia`, `python`, and `pip` build requests satisfy enforced ordering.
- Simple pinned pip specs such as `numpy==1.26.4`, `pandas==2.2.2`, and `scikit-learn~=1.5` are allowed.
- System layers require at least one valid Debian apt package name and have no parent.
- NVIDIA layers use the official CUDA network repository keyring flow, install compute-only open kernel module packages for an allowed numeric branch, emit an install manifest, and fail if unexpected non-`/usr` payload paths would be silently ignored by current activation.
- Python runtime layers cannot include pip or apt packages.
- Pip package layers cannot reinstall Python, cannot include apt packages, and must have a parent lineage containing a Python artifact.

- Root layer builds can be submitted for Ubuntu 18.04, 20.04, 22.04, or 24.04 and boot the configured image for that base.
- Python and pip child builds inherit the parent Ubuntu base and persist the inherited key on the build and artifact rows.
- Default consume VM creation boots the configured image for the profile's single normalized Ubuntu base.
- Mixed-base child lineages and mixed-base consume profiles are rejected before OpenStack side effects.