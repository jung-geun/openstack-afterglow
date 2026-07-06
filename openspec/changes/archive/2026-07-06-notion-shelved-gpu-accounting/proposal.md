# notion-shelved-gpu-accounting

## Goal
Notion GPU Spec usage and instance GPU map relations must stop counting `SHELVED` and `SHELVED_OFFLOADED` instances as allocated GPU consumers.

## Scope
- Add a shared backend resource-allocation status helper for Notion sync paths.
- Preserve shelved instance status, flavor, and visible GPU display metadata while clearing allocated-resource relations and counts.
- Share GPU usage aggregation between the periodic Notion worker and manual admin Notion sync.
- Pin the behavior with backend tests for `GPU map` relation clearing and `build_gpu_usage_by_gpu` aggregation.

## Non-goals
- No Notion schema/property name changes.
- No API path changes.
- No frontend component changes.
- No Placement reconciliation or GPU inventory math changes outside Notion sync payload/accounting.
