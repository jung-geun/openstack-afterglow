## Implementation

- [x] Move `WizardFooter` outside the wizard body flow into a responsive flex column.
- [x] Pin the footer within the existing `SlidePanel` scroll container.
- [x] Reorder mobile actions to 이전/취소/다음 and preserve desktop controls.
- [x] Keep the footer opaque, token-compatible with the dark panel, and safe-area aware.
- [x] Preserve unique tutorial navigation anchors and button handlers.
- [x] Add responsive footer regression coverage.

## Verification

- [x] Focused wizard tests pass (7 tests).
- [x] Frontend design guard passes (74 tests).
- [x] Full frontend suite passes (879 tests).
- [x] Frontend production build passes.
- [x] Browser route smoke reaches `/login` at desktop and mobile viewport sizes; authenticated visual interaction remains unavailable in the local environment.
