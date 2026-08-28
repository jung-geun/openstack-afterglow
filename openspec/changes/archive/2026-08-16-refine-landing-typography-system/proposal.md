## Why

The redesigned landing page currently uses MaruBuri for both large display headings and reading copy. Its literary serif character weakens the technical, operational tone of a research cloud product, while small UI and metadata fall back to font families that are declared but not actually bundled. The page needs explicit typography roles that improve Korean readability, preserve product character, and load predictably without depending on a runtime CDN.

## What Changes

- Research current open-licensed Korean display and interface typefaces using official sources, including performance and webfont availability.
- Define shared display, reading/UI, and operational-mono font roles in the authoritative design tokens and document when each role is used.
- Replace the landing page's all-purpose serif treatment with role-specific typography and tune line height, tracking, wrapping, and text measure at each responsive tier.
- Audit existing landing illustrations and generate a new image only if typography changes reveal a genuine explanatory gap; do not add decorative imagery.
- Add focused typography guardrails and visually verify light/dark mobile, tablet, and desktop states.

## Capabilities

### New Capabilities

- A locally hosted, role-based Korean typography system for public/editorial surfaces.

### Modified Capabilities

- Landing-page hierarchy and readability across display headings, body copy, labels, metadata, and operational identifiers.

## Impact

Expected changes are limited to shared font tokens/assets, the landing composition, design documentation, and focused tests. Application-console structure and behavior remain unchanged. Font assets must be open-licensed, WOFF2 where available, loaded with `font-display: swap`, and small enough to avoid an unreasonable public-page payload.
