## Why

The current public introduction page explains Afterglow's research-cloud scope, but its oversized editorial typography, decorative collage composition, and repeated card treatments make the product feel like a generic campaign site. The first page should instead communicate the concrete operational system: requests enter, policy-bound resources are allocated, workloads are observed, and reusable environments return to the team.

## What Changes

- Redesign the public root landing page around a product-specific research operations board rather than decorative landing-page motifs.
- Preserve the existing product content, authentication-aware console destination, runtime branding, workflow filtering, contact path, and inline theme-aware product artwork.
- Recompose the overview, capability, workflow, method, product-proof, audience, contact, and footer surfaces with a disciplined dark-first visual hierarchy.
- Add one purposeful interactive hero scenario control and keep the existing workflow filter so HTML, CSS, and Svelte state demonstrate the product model directly.
- Implement explicit mobile, tablet, and desktop compositions, visible focus, skip navigation, scrollspy, and reduced-motion behavior.
- Update landing tests and the design-system documentation for the revised public editorial composition.

## Capabilities

### New Capabilities

- Interactive research-operations hero board that maps a selected research scenario to policy, infrastructure, and reusable-output states.
- Responsive public-page composition designed specifically for research cloud delivery and operational proof.

### Modified Capabilities

- Public landing navigation, content sections, workflow filtering, console proof, contact CTA, and footer retain their functional contracts in a new visual system.
- Editorial design guidance documents the operations-board signature and responsive landing hierarchy.

## Impact

- Primary implementation: `frontend/src/lib/components/landing/LandingPage.svelte` and a focused landing-only hero board component.
- Tests: landing component contracts, root-route source contracts, responsive source guardrails, and design-system rules where necessary.
- Design system: existing semantic colors, typography, motion, button, card, and editorial tokens remain authoritative; no raw feature colors or new general-purpose primitive are introduced.
- No backend API, authentication flow, deployment setting, or persistent data changes.
