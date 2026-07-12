---
layout: default
title: Drover K3s 생성 workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 2
---

# Drover K3s 생성 workflow

**진입점:** `frontend/src/routes/dashboard/drover/+page.svelte`는 progress controller와 cluster list controller를 만들고 create modal에 `createCluster` action을 전달한다.

## Sequence

```mermaid
sequenceDiagram
actor User
participant Route as /dashboard/drover
participant Modal as K3sCreateClusterModal
participant Controller as K3sClusterListController
participant SSE as streamK3sProgress
participant API as /api/v1/k3s/clusters/async
participant Progress as K3sProgressController
participant Toast as toast

User->>Modal: cluster form 제출
Modal->>Controller: createCluster(form)
Controller->>Progress: begin(create)
Controller->>SSE: POST async endpoint with form body
SSE->>API: authenticated SSE request
loop progress message
  API-->>SSE: step/status/error
  SSE-->>Controller: K3s progress message
  Controller->>Progress: apply(message)
  Controller->>Toast: step 또는 완료/실패 안내
end
Controller->>Progress: end()
Controller->>Controller: fetchClusters()
```

## 시나리오 클래스

```mermaid
classDiagram
class K3sCreateModalModule["frontend/src/lib/components/dashboard/drover/K3sCreateClusterModal.svelte"] {
  <<component>>
}
class K3sListControllerModule["frontend/src/lib/stores/k3sClusterListController.svelte.ts"] {
  <<module>>
  +createK3sClusterListController()
  +createCluster()
  +fetchClusters()
}
class K3sProgressModule["frontend/src/lib/stores/k3sProgress.svelte.ts"] {
  <<module>>
}
class K3sCluster["frontend/src/lib/types/k3s.ts::K3sCluster"] {
  <<interface>>
}
class K3sClusterListOpts["frontend/src/lib/stores/k3sClusterListController.svelte.ts::K3sClusterListOpts"] {
  <<interface>>
}
class K3sSseStreamModule["frontend/src/lib/api/k3sSseStream.ts"] {
  <<module>>
  +streamK3sProgress()
}

K3sCreateModalModule --> K3sListControllerModule : passes onCreate
K3sListControllerModule --> K3sClusterListOpts : receives auth/progress options
K3sListControllerModule --> K3sProgressModule : updates progress
K3sListControllerModule --> K3sSseStreamModule : consumes
K3sListControllerModule --> K3sCluster : refreshes list
```

## 근거

- `k3sClusterListController.svelte.ts::createCluster`는 `streamK3sProgress('/api/v1/k3s/clusters/async', { method: 'POST', body })`를 사용한다.
- 같은 controller는 completion/failure toast를 표시하고 finally에서 목록을 재조회한다.
