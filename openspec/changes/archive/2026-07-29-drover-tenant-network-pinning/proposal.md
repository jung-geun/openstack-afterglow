## Why

Newly provisioned K3s nodes currently derive their address from the default route or `hostname -I`, so a secondary NIC can change the node InternalIP, Flannel transport, callback address, and API endpoint. The existing NIC attach behavior also needs an explicit primary-network invariant.

This change follows the completed `openspec/changes/archive/2026-05-18-38-k3s-nic-attach-default/` work by pinning the exact persisted `K3sCluster.network_id` during first boot and making later NIC activation route-neutral.

## What Changes

- Thread the immutable cluster network ID through every Ubuntu and FCOS K3s server/agent renderer and provisioning caller.
- Resolve the primary NIC from Nova `network_data.json`, persist a validated interface/IP plus K3s config drop-in atomically, and reuse it across retries and reboots.
- Make server installation, agent joins, callbacks, HA addresses, and Flannel consume the persisted pin instead of route-based address discovery.
- Configure secondary NICs with route-neutral DHCP/NetworkManager profiles on Ubuntu and FCOS.
- Enforce primary-aware attach/detach API behavior, audit rejected operations, and expose `is_primary` in the UI.
- Add focused backend/frontend regression coverage and register the frontend target.

## Impact

Existing VMs are unchanged because their baked cloud-init/Ignition is not rerun. New VMs, later scale/nodegroup VMs, and HA join servers receive the invariant. No database migration or HA join-server resource-discovery API is added.
