# Library Layer Promotion

## Goal

Promote the squashfs layer workflow to the admin Library Management surface and retire the old admin prebuilt-library page/API.

## Scope

- Move the squashfs layer admin UI from `/admin/layers` to `/admin/libraries`.
- Remount the squashfs layer admin API from `/api/v1/admin/layers` to `/api/v1/admin/libraries`.
- Remove the old admin prebuilt-library page/router that previously owned the admin Library Management name.
- Rename the file-storage prebuilt-share management page so it no longer presents itself as Library Management.
- Update focused backend/frontend regression coverage and relevant admin API documentation.

## Non-goals

- Do not remove shared `/api/v1/libraries` or VM wizard/prebuilt file-storage flows.
- Do not delete persisted prebuilt library models/services that are still used by VM provisioning and file-storage build flows.
- Do not keep a backend compatibility alias for `/api/v1/admin/layers`.
