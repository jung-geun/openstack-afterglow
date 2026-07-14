---
layout: default
title: Block volume workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 5
---

# Block volume workflow

**진입점:** `frontend/src/routes/dashboard/volumes/+page.svelte`는 `VolumesController`를 만들고 create modal 완료 callback으로 volume 목록을 다시 읽는다.

## Sequence

```mermaid
sequenceDiagram
actor User
participant Route as /dashboard/volumes
participant Modal as VolumeCreateModal
participant Mut as apiMut
participant API as /api/v1/volumes
participant Controller as VolumesController
participant List as VolumeListTable

Route->>Controller: fetchAll()
Controller->>API: GET volumes, snapshots, quotas
API-->>Controller: Volume[] + Snapshot[] + quotas
User->>Modal: name + size form 제출
Modal->>Mut: apiMut(volume create)
Mut->>API: POST /api/v1/volumes
API-->>Modal: created volume
Modal->>Controller: onCreated() -> fetchVolumes()
Controller->>API: GET /api/v1/volumes
Controller-->>List: refreshed Volume[]
```

## 시나리오 클래스

```mermaid
classDiagram
class VolumesRouteModule["frontend/src/routes/dashboard/volumes/+page.svelte"] {
  <<route>>
}
class VolumesControllerModule["frontend/src/lib/stores/volumesController.svelte.ts"] {
  <<module>>
  +createVolumesController()
  +fetchAll()
  +fetchVolumes()
}
class VolumeCreateModalModule["frontend/src/lib/components/volume/VolumeCreateModal.svelte"] {
  <<component>>
}
class ApiClientModule["frontend/src/lib/api/client.ts"] {
  <<module>>
}
class Volume["frontend/src/lib/types/volume.ts::Volume"] {
  <<interface>>
}
class Snapshot["frontend/src/lib/types/volume.ts::Snapshot"] {
  <<interface>>
}

VolumesRouteModule --> VolumesControllerModule : creates
VolumesRouteModule --> VolumeCreateModalModule : passes onCreated
VolumesControllerModule --> ApiClientModule : loads resource state
VolumesControllerModule --> Volume : owns list state
VolumesControllerModule --> Snapshot : owns list state
VolumeCreateModalModule --> ApiClientModule : creates volume
```

## 근거

- `volumes/+page.svelte`는 `createVolumesController`를 만들며 create callback으로 `ctrl.fetchVolumes()`를 전달한다.
- `VolumeCreateModal.svelte`는 `/api/v1/volumes` POST 후 callback을 호출한다.
- `VolumesController.fetchAll`은 volume, snapshot, quota, auto-backup config를 병렬 조회한다.
