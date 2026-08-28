## Implementation Tasks

- [x] Add typed administrator subnet detail models for pools, IP allocations, ports, DHCP agents, and data availability.
- [x] Aggregate subnet, network, port binding, and DHCP agent scheduling data in the Neutron service with deterministic ordering and graceful extension fallback.
- [x] Add the administrator-only subnet detail endpoint with explicit 404 and upstream failure handling.
- [x] Add backend service and API regressions for pool boundaries, port/IP/node correlation, DHCP agent mapping, extension fallback, and authorization.
- [x] Add frontend subnet detail types and a responsive administrator route using existing design primitives.
- [x] Link subnet summaries on administrator network detail pages to the new route without interfering with edit/delete actions.
- [x] Add frontend regressions for requested operational fields, empty/partial data, navigation, and responsive table semantics.
- [x] Separate allocated IP and port inventories into paginated sub-resource tabs to bound page length.
- [x] Run focused backend/frontend targets, browser verification at mobile/tablet/desktop, and the repository gate.
- [x] Archive the completed OpenSpec change without a specs layer.
