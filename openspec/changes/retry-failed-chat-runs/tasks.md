## Implementation Tasks

- [x] Trace persistent and pre-persistence chat failure states and define a retryable-turn contract.
- [x] Reuse the owner-scoped regeneration execution path with the failed user-turn ID, never duplicating user input.
- [x] Expose retryability for the latest failed/canceled durable run in the chat message tree response.
- [x] Add a visible retry action and local failed-draft recovery state using the existing ChatBubble action footer.
- [x] Add backend and frontend regression tests for retry, ownership, duplicate clicks, and pre-persistence send failure.
- [ ] Run focused tests and browser QA for failure-to-retry recovery.
