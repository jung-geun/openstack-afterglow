# Show provider segmentation on admin network details

## Goal
Let administrators identify the Neutron provider-network implementation of VLAN- and VXLAN-backed tenant networks without exposing provider metadata through ordinary user network APIs or pages.

## Scope
- Add an admin-only network detail response model containing `provider_network_type`, `provider_segmentation_id`, and `provider_physical_network`.
- Populate those fields from the OpenStack SDK `Network` resource while preserving the existing ordinary-user `NetworkDetail` response unchanged.
- On the administrator network detail card, show the provider type and conditional segmentation label: `VLAN 태그` for VLAN and `VXLAN VNI` for VXLAN.
- Show the physical network when Neutron returns it; show an em dash when a VLAN/VXLAN segmentation ID is unavailable.
- Make the basic-information grid one column on mobile and two columns from tablet upward.

## Constraints
- `/api/v1/networks/{id}` and all ordinary-user network UI surfaces must not receive or render provider metadata.
- `/api/v1/admin/networks/{id}` remains protected by `require_admin` and always serializes the three provider keys, using `null` when Neutron omits them.
- Use existing semantic design tokens and the `Card` primitive; introduce no new color, status, motion, or breakpoint contract.
- Preserve existing network/subnet/router behavior and avoid a second Neutron network lookup.

## Success criteria
- Admin VLAN and VXLAN network details show the correct type-specific ID label and value.
- Missing provider data renders safely without `undefined` and without exposing fields to ordinary users.
- Backend and frontend regression tests cover VLAN, VXLAN, missing metadata, admin authorization, and user-response isolation.
- Mobile, tablet, and desktop layouts retain all information without clipping.
