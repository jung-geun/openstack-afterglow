## Why

The redesigned public landing page now has a clearer product story, but it needs a rendered, breakpoint-by-breakpoint design audit before it can serve as a stable system reference. The review must catch visual hierarchy, density, typography, interaction, theme, and responsive problems that source-level tests cannot reveal.

## What Changes

- Audit the live landing page at mobile, tablet, desktop, and dark-mode states using repeatable browser evidence.
- Compare the rendered result with `DESIGN.md`, the shared token and primitive contracts, and the public-page anti-slop rules.
- Fix concrete visual and systemic inconsistencies in the landing composition while preserving its content and research-operations identity.
- Re-run browser, component, design-system, build, and repository-required verification after the fixes.

## Capabilities

### New Capabilities

- None. This change hardens the existing landing experience.

### Modified Capabilities

- Public landing presentation: improve visual hierarchy, responsive composition, interaction affordances, and design-system alignment based on rendered evidence.

## Impact

The change is limited to the public landing implementation, its focused tests, and design documentation only when a reusable contract needs clarification. It does not alter authenticated application behavior, APIs, or infrastructure.
