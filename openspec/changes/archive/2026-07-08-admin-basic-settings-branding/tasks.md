# Tasks

- [x] Create OpenSpec change record
- [x] Move login branding to basic settings
- [x] Add admin settings navigation
- [x] Apply Kubernetes drover icon
- [x] Run focused frontend verification

## Verification notes

- [x] `npm run test -- src/routes/__tests__/admin-basic-settings-branding.test.ts src/lib/components/admin/__tests__/AdminLoginBrandingPanel.test.ts`
- `npm run check -- --threshold error` — fails on existing unrelated frontend type errors outside this change set; no diagnostics point at `src/routes/admin/settings/+page.svelte`, `src/routes/admin/+page.svelte`, `src/lib/components/AdminSidebar.svelte`, `src/lib/config/nav.ts`, `src/lib/config/routes.ts`, `src/lib/components/dashboard/overview/DashboardStatTiles.svelte`, or `src/lib/components/dashboard/drover/K3sClusterCard.svelte`.
