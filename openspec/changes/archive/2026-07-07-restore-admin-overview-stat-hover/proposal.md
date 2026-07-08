# restore-admin-overview-stat-hover

## Goal

관리자 개요의 사용자/프로젝트/역할/그룹 카드에 사라진 링크 hover/focus 효과를 복구한다.

## Scope

- `frontend/src/lib/components/ui/StatTile.svelte`: linked StatTile hover/focus styling restored at the component layer.
- `frontend/src/lib/components/ui/__tests__/StatTile.test.ts`: regression coverage for anchor-gated hover contract.

## Root cause

The design-system `StatTile` rewrite moved `background` and `border` ownership into scoped `.stat-tile` CSS. The admin overview route still passed Tailwind `hover:border-* hover:bg-*` classes into `StatTile`, but the component-scoped base CSS won the cascade, so linked identity cards no longer changed on hover.

## Non-goals

- Do not restyle unrelated admin overview KPI cards.
- Do not make passive/non-linked `StatTile` cards look clickable.
- Do not chase unrelated repository-wide Svelte check failures.
