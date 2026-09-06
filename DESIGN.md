# Afterglow Design System

## Product character & authority

Afterglow is a dark-first cloud operations console: navy/ink surfaces support dense operational work, warm orange identifies the single highest-priority brand action, and blue/purple carry data and everyday operational intent. Light mode remaps the same semantic hierarchy; it is not a separate brand.

New UI follows this authority order: `frontend/src/routes/layout.css` owns theme and runtime CSS values; `frontend/src/lib/design/tokens.ts` exposes TypeScript metadata; `frontend/src/lib/components/ui` owns reusable behavior and markup; feature routes and components compose those primitives. `:root.light` legacy palette overrides are a compatibility boundary for existing visual debt, never a new API.

## Foundations

### Theme and color

| Token | Dark | Light | Meaning |
| --- | --- | --- | --- |
| `--color-surface-canvas` | `#06080d` | `#fafbff` | page canvas |
| `--color-surface-base` | `#0b0f17` | `#ffffff` | base panels/sidebar |
| `--color-surface-raised` | `#10141d` | `#ffffff` | cards, modal panels, popovers |
| `--color-surface-sunken` | `#161b27` | `#f4f6fb` | controls, inset rows, hover fills |
| `--color-surface-scrim` | `rgb(0 0 0 / 60%)` | `rgb(0 0 0 / 25%)` | modal/dialog scrim |
| `--color-surface-scrim-soft` | `rgb(0 0 0 / 50%)` | `rgb(0 0 0 / 20%)` | drawer/sidebar scrim |
| `--color-ink-0` / `--color-ink-1` / `--color-ink-2` / `--color-ink-3` | `#f4f6fb` / `#c8cfdc` / `#8a93a4` / `#5b6275` | `#0f172a` / `#1e293b` / `#475569` / `#94a3b8` | primary through disabled text |
| `--color-line` / `--color-line-2` | `#1e2533` / `#262e3f` | `#e2e8f0` / `#cbd5e1` | ordinary/control borders |
| `--color-accent` / `--color-accent-2` | `#7da3ff` / `#9f7df0` | `#2563eb` / `#6d28d9` | blue action/data and purple secondary data |
| `--color-warm` / `--color-warm-2` | `#f4976c` / `#e8c19a` | `#ea580c` / `#c2410c` | brand CTA and warm contrast |
| `--color-state-success` / `--color-state-warning` / `--color-state-danger` / `--color-state-info` / `--color-state-neutral` | `#5ddca0` / `#f4b85a` / `#f06b6b` / `#5ed4e4` / `#8a93a4` | `#16a34a` / `#b45309` / `#dc2626` / `#2563eb` / `#64748b` | operational state tones |
| `--color-warm-text` / `--color-state-success-text` | `var(--color-warm)` / `var(--color-state-success)` | `#c2410c` / `#15803d` | WCAG AA-safe brand and success text at normal sizes |

Use `SURFACE_CSS_VAR` rather than spelling surface variables in TypeScript-driven styles. Modal/dialog shells use `bg-surface-scrim`; drawers and sidebars use `bg-surface-scrim-soft`. `ConfirmDialog` intentionally keeps its canvas wash (`color-mix(in oklab, var(--color-surface-canvas) 72%, transparent)`) because it is not a black scrim.

Map legacy colors by role: gray/slate becomes surface, ink, or line; blue → accent; green → success; red → danger; yellow/amber → warning; orange → warm; purple/violet → accent-2. Do not collapse rose, indigo, cyan, sky, or teal into a generic tone: introduce a semantic token and primitive first when required. `CHART_COLORS`, topology external/shared/internal/router/link colors, and GitLab `#FC6D26`/`#E24329` are domain or third-party-brand exceptions only.

### Type, spacing, geometry, and elevation

Typography has three explicit roles and no feature may redeclare a Korean-only font family. `--font-sans` is locally hosted Pretendard Variable for Korean body copy, controls, tables, and dense console UI. `--font-display` is locally hosted IBM Plex Sans KR for public-page hero, section, and editorial headings only; do not use it for ordinary console page titles or controls. `--font-mono` is locally hosted IBM Plex Mono followed by Pretendard, so Latin identifiers, timestamps, resource values, and status labels keep a technical rhythm while Korean glyphs remain legible. All bundled fonts use WOFF2 and `font-display: swap`; do not add a runtime font CDN dependency. Keep the active system to these three families unless this document and its guardrails are updated first.

The console scale is page title `1.375rem`/700; emphasis count `0.9375rem`/700; form controls, `Button lg`, and PageHeader body `0.875rem`; `Button md`, `Button icon`, and PageHeader subtitle `0.8125rem`; Field label/help/error, Pagination, UsageBar meta, `Button sm`, and Toggle sm `0.75rem`; breadcrumbs, uppercase section labels, `Button xs`, Toggle xs, and Pill sm `0.6875rem` (500 with tracking for labels); Pill xs `0.625rem`. Body copy defaults to 400 with a relaxed line-height; dense labels use 500 or 600 rather than synthetic bold. Update this document before adding another type size or role.

`PageShell` defaults to `80rem`; route padding is `1rem` mobile and `2rem` desktop (`0.75rem`/`1rem` dense). Button and controls use `0.5rem` radius, Card `1rem`, TableShell `0.875rem`, and chips/pills `999px`. Card padding is `none/sm/md/lg = 0/0.75/1/1.5rem`. Ordinary surfaces use `1px solid var(--color-line)` with no shadow; controls use `--color-line-2`; only `Card surface="modal"` may elevate, while primary/accent actions may glow. Focus is `--focus-ring = 0 0 0 3px var(--accent-ring)`; removing an outline is allowed only when the same visible focus ring replaces it. Use Tailwind spacing/type values before creating new CSS variables.

### Layering and focus

`LAYER_CSS_VAR` exposes the runtime order: `--z-sidebar: 30`, `--z-panel: 40`, `--z-modal: 50`, `--z-toast: 60`, `--z-command: 200`, `--z-popover: 210`. Sidebar/AdminSidebar use sidebar; SlidePanel uses panel; ProjectQuotaPanel uses panel for scrim and modal for content; Modal uses modal; Toast and BulkSelectionOverlay use toast; CmdPalette uses command with its panel at `calc(var(--z-command) + 1)`; ConfirmDialog uses command; ActionMenu uses popover. In a shared stacking context, backdrop precedes panel in DOM order.

### Gradients and chrome

`--gradient-brand` is logo, brand text, and highlight only. `--gradient-warm` is `Button variant="primary"` and the one highest-priority CTA per surface. `--gradient-usage`, `--gradient-usage-warning`, and `--gradient-usage-danger` are quantitative bars only. `--warm-soft`/ring and `--accent-soft`/ring are their semantic tint, focus, and selection; `--admin-tone*` belongs only to admin context. Reuse global `--scrollbar-size`, `--scrollbar-track`, `--scrollbar-thumb`, and `--scrollbar-thumb-hover`; do not add component-scoped scrollbar styling.

## Layout & responsive hierarchy

Use the existing Tailwind breakpoints only: mobile is `<768px`; tablet is `md` (`768–1023px`); desktop is `lg` (`≥1024px`). `sm` (`≥640px`) is a compact mobile refinement, not a separate layout tier; use `xl` only to increase density after the desktop hierarchy already works. Do not introduce a component-specific breakpoint without updating this section and its test.

**Mobile (<768px).** `PageShell` route/dense padding is `1rem`/`0.75rem`. Navigation opens as the hamburger-controlled, dismissible sidebar drawer; PageHeader keeps its compact breadcrumb. Start resource and form layouts as one column; a two-column compact statistic group is allowed when each value remains readable. Header actions wrap or stack rather than clip, and the highest-priority action remains visible without hover. `TableShell` stays horizontally scrollable with headers intact; do not silently transform a table into cards unless the route provides and tests an equivalent semantic card view. SlidePanel and other task panels use the available viewport width with a visible close path.

**Tablet (768–1023px).** `PageShell` route/dense padding becomes `2rem`/`1rem`. The 15rem sidebar is sticky, PageHeader restores its full breadcrumb, and header actions retain the mobile wrap/stack composition; its sidebar search remains the compact search entry point. Use two columns for comparable cards/forms where each control has usable inline space; keep summary data legible instead of forcing desktop-density grids. Detail panels may adopt their component’s `md:` constrained width, but must retain panel-above-backdrop contrast and the existing dismissal contract.

**Desktop (≥1024px).** Keep the same PageShell padding and persistent sidebar. The header exposes its desktop search and project/context controls. Three-or-more columns are allowed only when the minimum card/control width and scanning order remain clear; use PageShell max widths instead of stretching sparse content. Inline action groups are appropriate when they do not truncate labels; preserve the mobile action order and accessible names.

Test every new or materially changed visual flow at mobile, tablet, and desktop widths. Confirm navigation, action placement, overlay sizing/dismissal, readable resource selection, and table overflow/card fallback at each relevant tier. Preserve information and interaction parity across widths; a smaller viewport may change composition, never silently remove required state or a reachable action.

## Actions

Use `Button`: `primary`, `accent`, `secondary`, `subtle`, `ghost`, `outline`, `danger`, `danger-outline`, or `link`; and sizes `xs`, `sm`, `md`, `lg`, or `icon`. Warm `primary` is one highest-priority CTA per surface. Blue `accent` is create/save/run and other routine operational work. `secondary`/`outline` are neutral actions; `subtle` compact chrome; `ghost`/`icon` utility actions; `danger`/`danger-outline` destructive entry or confirmation; `link` inline navigation. `href` renders an anchor; a missing/falsy href renders a native button. Icon-only `Button size="icon"` requires `ariaLabel`.

The current disabled anchor guards its primary click handler and intent callback, but keeps `href` and does not set `tabindex="-1"`; do not claim that middle-click, context menus, or keyboard navigation are fully blocked. Button has no loading prop: callers compose `disabled` with an accurate label.

## Forms

Compose forms with `Field` plus `TextInput`, `SelectInput`, or `TextareaInput`; use `FormModal` and `ConfirmDialog` for submit/cancel flows. `ToggleGroup` owns compact mutually exclusive filter/view choices: callers supply `value`, `options`, and `onchange` rather than recreating segmented controls. Field owns visible label/help/error copy and `for`/`id`; input primitives own placeholder, disabled, and focus appearance. Field help/error currently does not wire `aria-describedby` or `aria-invalid` to inputs: this is known accessibility debt, not implemented error announcement. Do not document imaginary error or loading props.

## Feedback/overlays/tables

Use `Alert`, `Toast`, and `EmptyState` for feedback; `StatusChip` + `getStatusStyle` and `Pill` for status; `TableShell` for tabular data. Modal is the scrim/dismissal shell and `Card surface="modal"` is the panel surface. Table density is normal `0.75rem × 1rem` or compact `0.5rem × 0.75rem`. UsageBar default thresholds are warning 80 and danger 95; it accepts `percent` or `value`/`max`, clamps invalid or out-of-range percentages to `0–100`, and for `max={-1}` labels the quota `무제한` without a percentage or fill. Use `UsageBar`, `QuotaBar`, or `CapacityBar` instead of route-specific bars.

`UsageRing` is the compact inline counterpart to `UsageBar`: use it only where a quantitative meter must share a narrow control row, such as the chat composer. It uses the same threshold contract, remains a `role="meter"` with an explicit text equivalent, and never replaces the full UsageBar on settings, quota, or detail surfaces.

## Status & data visualization

Operational status uses exact, case-sensitive `getStatusStyle(status: string | null | undefined)` and its five tones; unknown or falsy status is neutral. Status conveys label plus tone and, where applicable, transition dot; color alone is never state. Charts use the six ordinal `CHART_COLORS`; topology preserves its domain colors.

## Motion

`MOTION_CSS_VAR`, `MOTION_DURATION_MS`, and `REDUCED_MOTION_QUERY` are the shared vocabulary. Fast `--motion-duration-fast: 150ms` + `--motion-ease-standard: ease` is hover/focus/color feedback. Base `--motion-duration-base: 200ms` is control movement, compact fills, and fades. Panel `--motion-duration-panel: 300ms` + `--motion-ease-out: ease-out` is drawer/fly/pop. Data `--motion-duration-data: 500ms` is long-form resource/build progress. Status pulse `--motion-duration-status-pulse: 1400ms` + `--motion-ease-in-out: ease-in-out` is status dots.

Animate opacity, translate, or scale only; never animate layout dimensions. Hover is decoration, never the only status signal. Repeating animation is limited to loading, progress, and status. `prefersReducedMotion()` and `motionDuration()` make JavaScript transitions immediate. The global reduced-motion contract sets all five duration variables plus Tailwind `--default-transition-duration` and `--default-animation-duration` to `0.01ms`, scroll to `auto`, and universally overrides animation/transition duration and delay.

Named motion exceptions: `--landing-ease`; ChatPanel composer `cubic-bezier(0.22, 1, 0.36, 1)`; QuotaDonut `duration-700`; 600ms landing reveal; 7-second tutorial hint; and `0.8–1.2s` linear loading loops. Do not copy exceptions into ordinary components.

## Editorial surfaces

`--gradient-editorial-canvas`, `--pattern-editorial-grid`, `--gradient-editorial-grid-mask`, `--gradient-editorial-cta`, and `--color-surface-editorial-media` belong to public/editorial surfaces. Approved external SVG plates may retain their embedded palette only when loaded through `<img>`. Approved panel composition: `Card surface="subtle"` is the surface around semantic outer capability/workflow articles; the method matrix is one Card around direct semantic step articles.

The public landing page is a research-operations surface, not a generic campaign template. Its signature is the interactive operations board: a selected research request is shown passing through policy checks into allocated infrastructure and a reusable output. IBM Plex Sans KR carries hero, section, capability, quotation, and contact display headings; Pretendard carries explanations, actions, and product UI; `--font-mono` is limited to timestamps, resource identifiers, compact status labels, and other operational metadata. Landing display type uses medium or semibold weights, restrained negative tracking, and fluid sizes between `2.75rem–4.25rem` for the hero, `2rem–3.75rem` for section headings, and `1.25rem–2rem` for editorial card headings. These public display sizes and the display family do not extend the application-console type scale.

Landing responsive composition follows the global tiers exactly. Mobile stacks the hero copy, scenario controls, policy checks, allocated resource, and reusable output in one reading order; the brand and compact console action share the first navigation row while 44px-tall navigation links scroll horizontally below them. Tablet keeps the hero copy above the full-width operations board, places section labels above their headings, and uses two columns only for capability and method pairs. Desktop places the hero copy beside the operations board and may move section labels into a stable left rail. The board retains its readable two-row desktop flow until the `xl` density refinement (`≥1280px`); only then may request, policy, and allocation expand into one row. The four capability stories form one divided two-by-two service matrix rather than cards with unequal spans: every cell has the same geometry, static cells do not use hover affordances, and artwork is contained inside a bounded media plate without cropping embedded captions. Workflow filters remain sticky only while their adjacent list is visible. Product artwork is evidence inside bounded console frames, never a rotated decorative collage. Static workflow summaries form one divided list rather than a stack of decorative cards. All content, actions, filter state, captions, and contact paths remain available at every tier.

## Chat messages

`ChatBubble` is the chat-message primitive. It supplies `chat-start`, `chat-end`, header, bubble, and optional action footer; features provide only content and actions. It owns `--chat-message-gap`, `--chat-message-meta-gap`, `--chat-message-meta-inset`, `--chat-message-meta-size`, `--chat-message-radius`, `--chat-message-directional-corner`, `--chat-message-padding-block`, `--chat-message-padding-inline`, `--chat-message-assistant-max-inline`, and `--chat-message-user-max-inline`. Do not recreate route-specific bubbles, sizes, or colors.

## Resource selection

Show a checkbox on both desktop and touch for selectable rows/cards. `SelectionCheckbox` owns checked, indeterminate, disabled, and unavailable-X semantics; `SelectionToolbar` owns the select-all control, selected count, and `onToggle`; `BulkSelectionOverlay` owns the selected-count, busy, and bulk-action presentation. `ActionMenu` owns the overflow trigger, fixed popover placement, outside-click/Escape dismissal; callers own its `open`, `onopen`, and `onclose` state. Unavailable resources show a disabled circular X in the same position and provide the reason. A screen owns one visible resource-domain selection state; tab/filter/project/domain changes clear selections outside the result. Use `BulkSelectionOverlay`, `bulk-selection-page`, `resource-selection-surface`, and `data-selected`; select-all includes only selectable IDs.

## Accessibility

Never communicate status, selection, loading, or disabled state through color or animation alone: pair visible text and the relevant attribute/reason. Maintain visible keyboard focus with `--focus-ring`. Do not state that Modal/Dialog focus trapping exists beyond the current shell; add it only by extending Modal with tests.

Normal-sized public/editorial labels use `--color-ink-2`, `--color-warm-text`, or `--color-state-success-text` so both themes retain WCAG AA contrast without changing the dark brand palette. Reserve `--color-ink-3` for disabled text and raw `--color-warm` / state tones for large display text or non-text decoration.

## New UI entity workflow & legacy debt

1. 새 색상·gradient·badge tone·table density·form control·card treatment가 필요하면 feature file 작성 전에 `layout.css`, `frontend/src/lib/design/tokens.ts`, `frontend/src/lib/components/ui/*`, tests, `DESIGN.md`를 먼저 갱신한다.
2. Primitive token/test work precedes feature composition; then run the visual-debt guardrail.
3. 새 route/component file은 raw hex, `bg-[#...]`, raw palette classes(`bg-blue-600`, `text-gray-400`, `border-red-700` 등)를 직접 추가하지 않는다. Existing debt is bounded by `frontend/src/lib/design/legacyVisualDebt.ts`; reduce it in separate visual-regression work rather than extending it.
4. Use `StatusChip` + `frontend/src/lib/config/statusColors.ts` for operational status. New inline ternary status colors are prohibited.
5. Use `frontend/src/lib/components/ui` for action, modal, table, form, card, and alert. If a primitive is insufficient, extend that primitive and update its tests and this document first.
