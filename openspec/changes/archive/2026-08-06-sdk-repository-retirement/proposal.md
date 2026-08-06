# SDK Repository Retirement

## Why

The SDK distributions now live inside their owning service repositories. The backend still copies two deleted standalone SDK paths during its Docker build, so a clean backend image cannot be built. The old GitHub repositories must remain available until no supported consumer depends on their historical Git URLs.

## What Changes

- Remove obsolete standalone Waygate and Drover SDK `COPY` instructions from the backend Docker build.
- Verify a clean-context backend image build.
- Audit organization-visible references to the legacy SDK repositories and define their safe retirement state.

## Impact

- Affected code: root `Dockerfile` backend-builder stage.
- Affected repositories: `waygate-sdk`, `drover-sdk`, and `lumen-sdk`.
- No SDK package name or import path changes.

## Retirement Decision

Organization-visible code has no remaining references to the three legacy SDK repository URLs, and none of the repositories has a fork. This does not establish that external users, private repositories, local clones, or deployment caches have migrated. Archive each public legacy repository first with a deprecation notice that names its replacement (`waygate/sdk`, `drover/sdk`, or `lumen/sdk`) and preserve it through a published deprecation window. Permanently delete only after that window ends and support confirms no remaining consumers.
