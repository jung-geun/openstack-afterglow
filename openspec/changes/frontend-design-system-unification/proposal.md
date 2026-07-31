## Why

Afterglow's token-backed primitives and legacy utility-era UI coexist without a complete, executable authority for new work. The result is inconsistent overlays, ad-hoc stacking, implicit motion timing, and duplicated AI-agent instructions.

## What Changes

- Rewrite `DESIGN.md` as the authoritative guide for the existing dark-first operations-console system, including theme, surface scrims, layering, primitive routing, accessibility limits, motion, and legacy-debt boundaries.
- Add token-backed overlay, z-index, and reduced-motion contracts; migrate the named canonical UI surfaces and motion consumers to those contracts.
- Consolidate repository AI-agent rules in `AGENTS.md` and replace `CLAUDE.md` with the relative `AGENTS.md` symlink.

## Capabilities

### New Capabilities

- Named surface scrim, layer, and motion token contracts available to UI primitives and feature composition.
- SSR-safe reduced-motion helpers for JavaScript-driven Svelte and Web Animation transitions.

### Modified Capabilities

- Canonical overlays and controls use semantic scrim, layer, and motion contracts instead of raw values.
- Design-system source-contract tests enforce the shared runtime, TypeScript, documentation, and agent-instruction authority.

## Impact

- Frontend runtime tokens, reusable UI components, representative overlays, chat and landing motion consumers, and design-system tests change.
- `DESIGN.md`, `AGENTS.md`, and the `CLAUDE.md` filesystem entry change.
- Existing legacy raw-color and raw-button debt remains outside this change's migration scope and stays bounded by the visual-debt guardrail.
