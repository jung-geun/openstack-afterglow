## Why

Drover 0.2.0 can start under the Afterglow Kolla plugin while remaining unready because the generated runtime configuration omits the resolved `drover-service` project ID. The new fail-closed readiness check rejects that deployment, and resource-policy updates cannot authenticate the service connection.

## What Changes

- Resolve the Drover service project ID through Kolla's existing `project_info` pattern before rendering `drover.conf`.
- Render the resolved ID into `[keystone].service_project_id` on every Drover controller.
- Add role contract coverage for lookup, fail-closed assertion, and rendered configuration.
- Reconfigure the live Drover deployment and verify service readiness independently from deferred live lifecycle scenarios.
- Remove live OpenStack scenarios from automatic push/PR CI and retain them as an explicit `workflow_dispatch` opt-in for later stable-environment or DevStack execution.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- Drover Kolla configuration now carries the concrete service-project scope required by service credentials and readiness checks.
- Layered CI remains deterministic without external OpenStack reachability; operators can still request the live scenario explicitly.

## Impact

Drover Kolla deploy/reconfigure resolves one existing Keystone project and recreates containers only when the rendered configuration changes. Missing or ambiguous `drover-service` projects fail before rendering instead of producing a live-but-unready API. Routine push/PR CI no longer depends on an external OpenStack deployment; the live scenario remains available only through an explicit manual input.
