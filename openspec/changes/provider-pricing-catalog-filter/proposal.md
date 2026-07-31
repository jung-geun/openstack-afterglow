## Why

The models.dev price-import dialog exposes every catalog provider in an arbitrary order. Administrators must scan unrelated providers to find the service configured in Afterglow, making price imports slow and prone to selecting the wrong catalog.

## What Changes

- Return the union of models.dev provider candidates that match registered LLM providers by existing catalog mapping first and normalized provider type/name second; prioritize the currently selected local provider's matches.
- Do not expose unregistered models.dev providers; administrators must register the corresponding service before its catalog can appear.
- Sort provider candidates deterministically and add a searchable provider control to the price-import dialog.

## Capabilities

### New Capabilities

- Filtered, sorted models.dev provider candidates for registered local providers, with the selected local provider's matches first.
- In-dialog provider search across only the registered-service catalog candidates.

### Modified Capabilities

- models.dev provider-list API accepts the selected local provider and returns only matching catalog candidates for registered providers.

## Impact

- Backend: models.dev catalog helpers, provider storage lookup, admin model-pricing routes, and route tests.
- Frontend: the chat model configuration price-import dialog and its tests.
- Existing imported provider mappings remain selectable even if their display name or provider type no longer matches the catalog.