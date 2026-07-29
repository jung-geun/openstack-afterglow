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

## Typography tokens

- `--font-sans`는 `MaruBuri`, `Geist`, `Inter`, `system-ui`, `sans-serif` 순서다. 한국어 본문과 제목은 사용자가 제공한 MaruBuri TTF를 `frontend/static/fonts/maruburi/` 경로로 서비스해 200/300/400/600/700 weight를 우선 사용하고, 라틴/미지원 글리프는 Geist/Inter로 fallback한다.
- 전역 `html, body`는 `font-family: var(--font-sans)`를 사용한다. 새 화면에서 한국어 전용 폰트를 다시 선언하지 말고 토큰을 재사용한다.

## Gradient rules

- `--gradient-brand: linear-gradient(135deg, var(--color-warm), var(--color-accent-2))`는 logo/brand text/highlight only.
- `--gradient-warm: linear-gradient(135deg, var(--color-warm), var(--color-warm-2))`는 `Button variant="primary"`와 one-primary-CTA-per-surface only.
- `--gradient-usage`, `--gradient-usage-warning`, `--gradient-usage-danger`는 quantitative usage bars only. Progress/usage 임계값 기본값은 warning `>=80`, danger `>=95`; 기존 특정 리소스가 다른 임계값을 쓰면 `UsageBar` props로 명시한다.

## Scrollbars

- Scrollbars are global, token-backed UI chrome: `--scrollbar-size`, `--scrollbar-track`, `--scrollbar-thumb`, and `--scrollbar-thumb-hover`.
- Use the global treatment rather than component-scoped scrollbar declarations. Tracks recede into their owning surface; thumbs remain visible enough for pointer use and lighten only on hover.

### Editorial public surfaces

- `--gradient-editorial-canvas`, `--pattern-editorial-grid`, and `--gradient-editorial-grid-mask` are public/editorial surfaces. They are dark-first but resolve through the standard color-token mapping under `html.light`.
- `--color-surface-editorial-media` is the theme-invariant dark canvas behind static editorial SVG plates. It keeps `contain` media complete without exposing light letterbox bands.
- `--gradient-editorial-cta` is limited to the single closing editorial panel; it never replaces `Button variant="primary"`.
- Approved external SVG plates may retain their equivalent embedded palette only when loaded through `<img>`.
- Approved panel composition: `Card surface="subtle"` is the visual surface around semantic outer capability/workflow articles; the method matrix is one Card around direct semantic step articles.

## Chat messages

- `ChatBubble` is the chat-message primitive. It provides the semantic `chat-start`/`chat-end`, header, bubble, and optional action footer structure; feature components supply only message content and actions.
- Direction is expressed with the compact directional corner token (`--chat-message-directional-corner`), not a pseudo-element tail. Start uses `--color-surface-raised` with `--color-line`; end uses `--color-accent` with `--color-action-on-accent`.
- The message primitive owns `--chat-message-*` spacing, radius, padding, and width tokens. Do not create per-route bubble sizes, colors, or duplicate chat structures.
- Shared values are `--chat-message-gap`, `--chat-message-meta-gap`, `--chat-message-meta-inset`, `--chat-message-meta-size`, `--chat-message-radius`, `--chat-message-directional-corner`, `--chat-message-padding-block`, `--chat-message-padding-inline`, `--chat-message-assistant-max-inline`, and `--chat-message-user-max-inline`.

## Resource selection

- 선택 가능한 행과 카드는 체크박스를 데스크톱·터치 환경 모두에서 항상 보이게 하며, hover로만 노출하지 않는다.
- 선택 불가 리소스는 같은 위치에 비활성화 원형 X 마크를 표시하고 이유를 `title`로 설명한다. square checkbox를 흐리게 재사용하지 않으며, select-all은 선택 가능한 ID만 포함한다.
- 한 화면에서 동시에 보이는 여러 리소스 도메인은 하나만 선택 상태를 소유한다. 탭·필터·프로젝트·도메인 전환은 현재 조회 결과에 없는 선택을 정리한다.
- 선택 작업은 `BulkSelectionOverlay` 하나로 고정한다. 페이지는 `bulk-selection-page` bottom clearance를 적용하고, 선택 surface는 `resource-selection-surface` 및 `data-selected`로 `--accent-soft`를 사용한다.

## New UI entity rules

1. 새 색상·gradient·badge tone·table density·form control·card treatment가 필요하면 feature file 작성 전에 `layout.css`, `frontend/src/lib/design/tokens.ts`, `frontend/src/lib/components/ui/*`, tests, `DESIGN.md`를 먼저 갱신한다.
2. 새 route/component file은 raw hex, `bg-[#...]`, raw palette classes(`bg-blue-600`, `text-gray-400`, `border-red-700` 등)를 직접 추가하지 않는다. 기존 legacy file은 baseline guardrail에 남아도 되지만 새 file은 실패한다.
3. Operational status는 `StatusChip` + `frontend/src/lib/config/statusColors.ts`를 확장한다. Inline ternary status color는 새로 만들지 않는다.
4. Button, modal, table, form, card, alert는 `frontend/src/lib/components/ui` primitive를 먼저 사용한다. primitive가 맞지 않으면 primitive를 확장하고 문서·테스트를 같이 갱신한다.
