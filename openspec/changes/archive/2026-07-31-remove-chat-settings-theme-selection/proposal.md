## Why

The chat settings modal duplicates the global theme control already available from every page header. Keeping both controls gives users two locations for one application-wide preference without adding a settings-specific capability.

## What Changes

- Remove the theme selector and its explanatory copy from chat settings.
- Keep theme switching available exclusively through the existing global header control.
- Preserve all non-theme chat settings sections and their navigation.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- Chat settings no longer exposes application theme selection.

## Impact

- Frontend chat settings modal and its component tests.
- No theme persistence, token, or global header behavior changes.
