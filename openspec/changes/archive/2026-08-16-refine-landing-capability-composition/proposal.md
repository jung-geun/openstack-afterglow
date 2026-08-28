## Why

The landing capability section currently mixes incompatible card proportions, illustration crops, text densities, and grid spans. At desktop width the first capability dominates without a clear product reason while the governance capability is stranded on a second row, making the section look partially loaded rather than intentionally composed. The section needs a cloud-product information pattern that feels operational and credible without copying another vendor's visual identity.

## What Changes

- Compare current official AWS, Google Cloud, and relevant AI infrastructure company landing pages for reusable composition principles such as service grouping, consistent card families, editorial hierarchy, and responsive density.
- Recompose the four existing capability stories into one coherent desktop system with intentional illustration bounds, consistent metadata and copy measure, and no orphaned card.
- Preserve all existing Afterglow capability content and semantic design tokens while removing visual mismatches visible in the supplied screenshot.
- Define and verify the mobile, tablet, desktop, dark-mode, focus, and reduced-motion behavior of the refined section.
- Add focused regression coverage for the layout contract and update the landing design documentation only where the system contract changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `public-landing-capability-composition`: The public landing page presents compute, cluster, reusable library, and governance capabilities as a coherent responsive product family rather than an irregular card mosaic.

## Impact

- Frontend-only changes scoped to the public landing components, their focused tests, and the documented landing composition contract.
- No backend, API, authentication, or application-console behavior changes.
- Existing unrelated worktree files remain untouched; implementation is verified through rendered before/after screenshots and repository-required tests.
