# frontend-design-system-rules

## Goal

frontend UI/UX design-system rules, reusable assets, and no-new-raw-color guardrail

## Scope

- `frontend/src/routes/layout.css`
- `frontend/src/lib/design/**`
- `frontend/src/lib/components/ui/**`
- `frontend/src/routes/__tests__/**`
- `frontend/src/lib/components/ui/__tests__/**`
- `DESIGN.md`
- `frontend/README.md`
- `AGENTS.md`
- Representative consumer files:
  - `frontend/src/lib/components/ui/FormModal.svelte`
  - `frontend/src/lib/components/ui/ConfirmDialog.svelte`
  - `frontend/src/lib/components/ui/Pagination.svelte`
  - `frontend/src/lib/components/AutoRefreshControl.svelte`
  - `frontend/src/lib/components/auth/LoginForm.svelte`
  - `frontend/src/routes/admin/+page.svelte`
  - `frontend/src/routes/admin/instances/+page.svelte`
  - `frontend/src/routes/admin/libraries/+page.svelte`

## Non-goals

- Do not one-shot restyle every frontend route.
- Do not replace the existing `theme` store, `resolvedTheme`, or `<html class="light">` theme path.
- Do not remove the existing `layout.css` legacy light-mode compatibility override table.
