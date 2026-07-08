# Afterglow Design System

Afterglow는 dark-first cloud operations UI다. 기본 감성은 고밀도 운영 콘솔, navy/ink surface, warm orange brand accent, cool blue/purple data accent다. Light mode는 별도 브랜드가 아니라 동일 정보 위계를 밝은 surface로 재매핑한 운영 모드다.

## Color tokens

| Token | Dark | Light | Usage |
| --- | --- | --- | --- |
| `--color-surface-canvas` | `#06080d` | `#fafbff` | app/page background |
| `--color-surface-base` | `#0b0f17` | `#ffffff` | sidebar/base panels |
| `--color-surface-raised` | `#10141d` | `#ffffff` | cards, modals, popovers |
| `--color-surface-sunken` | `#161b27` | `#f4f6fb` | inputs, inset rows, hover fills |
| `--color-ink-0` | `#f4f6fb` | `#0f172a` | primary text |
| `--color-ink-1` | `#c8cfdc` | `#1e293b` | secondary text |
| `--color-ink-2` | `#8a93a4` | `#475569` | muted text/icons |
| `--color-ink-3` | `#5b6275` | `#94a3b8` | disabled/subtle text |
| `--color-line` | `#1e2533` | `#e2e8f0` | default border |
| `--color-line-2` | `#262e3f` | `#cbd5e1` | strong/focus-adjacent border |
| `--color-accent` | `#7da3ff` | `#2563eb` | primary data/action blue |
| `--color-accent-2` | `#9f7df0` | `#6d28d9` | secondary data/purple |
| `--color-warm` | `#f4976c` | `#ea580c` | brand warm/orange |
| `--color-warm-2` | `#e8c19a` | `#c2410c` | warm contrast/hover |
| `--color-state-success` | `#5ddca0` | `#16a34a` | healthy/active/success |
| `--color-state-warning` | `#f4b85a` | `#b45309` | pending/warning |
| `--color-state-danger` | `#f06b6b` | `#dc2626` | error/destructive |
| `--color-state-info` | `#5ed4e4` | `#2563eb` | info/in-progress stable |
| `--color-state-neutral` | `#8a93a4` | `#64748b` | neutral/unknown |

## Gradient rules

- `--gradient-brand: linear-gradient(135deg, var(--color-warm), var(--color-accent-2))`는 logo/brand text/highlight only.
- `--gradient-warm: linear-gradient(135deg, var(--color-warm), var(--color-warm-2))`는 `Button variant="primary"`와 one-primary-CTA-per-surface only.
- `--gradient-usage`, `--gradient-usage-warning`, `--gradient-usage-danger`는 quantitative usage bars only. Progress/usage 임계값 기본값은 warning `>=80`, danger `>=95`; 기존 특정 리소스가 다른 임계값을 쓰면 `UsageBar` props로 명시한다.

## New UI entity rules

1. 새 색상·gradient·badge tone·table density·form control·card treatment가 필요하면 feature file 작성 전에 `layout.css`, `frontend/src/lib/design/tokens.ts`, `frontend/src/lib/components/ui/*`, tests, `DESIGN.md`를 먼저 갱신한다.
2. 새 route/component file은 raw hex, `bg-[#...]`, raw palette classes(`bg-blue-600`, `text-gray-400`, `border-red-700` 등)를 직접 추가하지 않는다. 기존 legacy file은 baseline guardrail에 남아도 되지만 새 file은 실패한다.
3. Operational status는 `StatusChip` + `frontend/src/lib/config/statusColors.ts`를 확장한다. Inline ternary status color는 새로 만들지 않는다.
4. Button, modal, table, form, card, alert는 `frontend/src/lib/components/ui` primitive를 먼저 사용한다. primitive가 맞지 않으면 primitive를 확장하고 문서·테스트를 같이 갱신한다.
