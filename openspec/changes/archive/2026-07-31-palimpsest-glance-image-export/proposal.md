## Why

Palimpsest local and remote builders can only pull cloud-image blobs that were already uploaded to the hub. Images that exist only in Glance—including Afterglow's raw base images—cannot be selected, converted, or downloaded through the Palimpsest workflow.

## What Changes

- Add a project-owned durable export queue that snapshots and revalidates Glance image access, streams source bytes to hub scratch storage, verifies Glance hashes, and records completed content-addressed artifacts.
- Add a dedicated worker that rejects external/backing-file references, runs bounded `qemu-img` conversion for raw, qcow2, VMDK, VDI, VHD, and VHDX, and safely resumes expired leases.
- Add project-isolated export status, authenticated Range download, and one-use browser download-ticket APIs under `/api/v1/palimpsest/hub`.
- Add `palimpsest image list` and one-command `palimpsest image pull --format ...`, plus a conversion/download section in the existing image detail panel.
- Mount a shared persistent hub volume in API and worker deployments and package `qemu-img` in the API image used by the export worker.

## Capabilities

### New Capabilities

- `palimpsest-glance-image-export`: export any currently visible active Glance image into a requested supported disk format, persist it as a project-owned hub artifact, poll durable progress, and download it through browser or CLI without buffering multi-gigabyte files in memory.

### Modified Capabilities

- Palimpsest cloud-image metadata and CLI upload filters accept raw, qcow2, VMDK, VDI, VHD, and VHDX instead of only raw/qcow2.
- Hub blob streaming uses format-aware safe filenames and preserves blobs referenced by either legacy hub rows or image-export records.

## Impact

- Adds migration `070_palimpsest_image_exports.sql`, a dedicated `palimpsest-worker` process, `qemu-utils` in the API image, and a shared RWX hub volume.
- General users may export only images visible to their current OpenStack project; authorization is checked both when queued and immediately before worker download.
- Existing flat Palimpsest CLI commands and direct digest pull behavior remain compatible.
