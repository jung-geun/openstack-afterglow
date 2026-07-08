# admin-flavor-gpu-filter-alias

## Goal

Add admin Flavor GPU alias filtering, make GPU catalog DB overrides authoritative for catalog/alias discovery, and record why CPU/RAM/Disk linear VM sizing is out of scope for this change.

## Scope

- Extend the existing admin Flavor GPU dropdown from GPU yes/no to include concrete GPU aliases parsed from flavor `pci_passthrough:alias` extra specs.
- Keep the existing `bind:gpuFilter` UI contract while changing reserved filter values to `''`, `__gpu__`, and `__non_gpu__`.
- Fix GPU catalog merge behavior so DB catalog rows override builtin/config device name, audio flag, and aliases when `(vendor_id, device_id)` matches.
- Refresh GPU catalog DB overlay before `/api/v1/admin/gpu-aliases` alias discovery so DB-updated aliases are visible without relying on stale in-process defaults.
- Add focused backend and frontend regression tests.

## Non-goals

- Do not implement CPU/RAM/Disk linear VM sizing in the VM creation request path.
- Do not change builtin GPU alias ordering, Helm/K8s default alias lists, or `GpuQuota.gpu_type` storage/merge/migration policy.
- Do not mutate existing OpenStack flavor `pci_passthrough:alias` extra specs.

## CPU/RAM/Disk sizing conclusion

Current VM creation sends only `flavor_id`: the frontend store posts `CreateInstanceRequest.flavor_id`, the backend model requires `flavor_id: str`, and Nova receives that value as `flavorRef`. Raw vCPU/RAM/Disk values cannot be sent directly to `nova.create_server` under this contract. Linear sizing is feasible only as a separate backend/admin workflow: either generate bounded admin-managed flavors from allowed grids, or match requested dimensions to existing flavors and return a clear no-match result.
