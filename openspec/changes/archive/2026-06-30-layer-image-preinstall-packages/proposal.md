# layer-image-preinstall-packages

## Goal

Document and centralize the OS packages that should be preinstalled into layer workflow builder/consumer images while keeping cloud-init package installation as an idempotent fallback.

## Scope

- Identify layer build VM, layer consume VM, and shared library builder cloud-init package dependencies.
- Add source-of-truth package constants used by runtime cloud-init fallback generation.
- Add a reusable cloud-config payload for baking layer workflow base images.
- Add regression tests that prevent package-list drift.

## Non-goals

- Do not remove cloud-init `packages:` fallback lines.
- Do not preinstall broader k3s/GPU/application packages into the layer builder image.
