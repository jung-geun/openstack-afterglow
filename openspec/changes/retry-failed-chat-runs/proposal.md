## Why

A chat submission or generation can fail after the user message is visible. The current UI only offers regeneration for an already completed assistant message, leaving a failed user turn with no direct recovery path.

## What Changes

- Preserve and expose durable failed-run state for the affected user turn.
- Add an owner-authorized retry path that reuses the persisted user input while creating a new idempotent run.
- Add a compact retry action next to a failed user message and a clear failure explanation without hiding the original message.
- Keep completed-assistant regeneration unchanged; retry is only for turns without a successful assistant result.
- Handle failures before durable persistence by retaining a local retryable draft until the request succeeds or the user dismisses it.

## Capabilities

### New Capabilities

- Users can retry a failed send or failed generation from the affected user turn.

### Modified Capabilities

- Chat message trees identify retryable failed turns and render their recovery action.

## Impact

- Chat completion API, durable-run persistence, message-tree response types, and chat message/window/panel UI change together.
- New backend and frontend tests cover ownership, idempotency, failed-run rendering, retry, and local submission failure.
