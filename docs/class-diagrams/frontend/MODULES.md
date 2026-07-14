---
layout: default
title: Frontend 모듈 관계
parent: 클래스 다이어그램
nav_order: 2
---

# `frontend` 상위 모듈 관계

`frontend/src`는 SvelteKit route를 사용자 작업의 진입점으로 두고, component·store/controller·API client·shared type을 조합한다. 이 문서는 하위 경로별 클래스 다이어그램과 workflow 문서를 연결한다.

## 모듈 관계

```mermaid
classDiagram
class Routes["src/routes\nSvelteKit page entry points"]
class Components["src/lib/components\nPanels · modals · controls"]
class Stores["src/lib/stores\nSvelte 5 state controllers"]
class API["src/lib/api\nAuthenticated HTTP · SSE"]
class Types["src/lib/types\nShared resource contracts"]
class Utils["src/lib/utils\nRefresh · mutation helpers"]
class Backend["backend /api/v1\nFastAPI resources"]

Routes --> Components : composes UI
Routes --> Stores : creates controllers
Components --> Stores : invokes actions
Stores --> API : loads and mutates
Routes --> API : simple page-local calls
Stores --> Types : state contracts
Components --> Types : prop contracts
Routes --> Utils : refresh and navigation helpers
API --> Backend : HTTP / SSE
```

## 대표 child module 타입 관계

```mermaid
classDiagram
class VmCreatePanelModule["frontend/src/lib/components/VmCreatePanel.svelte"] {
  <<component>>
}
class VmCreateStoreModule["frontend/src/lib/stores/vmCreateStore.svelte.ts"] {
  <<module>>
}
class ProgressMessage["frontend/src/lib/stores/vmCreateStore.svelte.ts::ProgressMessage"] {
  <<interface>>
}
class DroverRouteModule["frontend/src/routes/dashboard/drover/+page.svelte"] {
  <<route>>
}
class K3sListControllerModule["frontend/src/lib/stores/k3sClusterListController.svelte.ts"] {
  <<module>>
}
class K3sCluster["frontend/src/lib/types/k3s.ts::K3sCluster"] {
  <<interface>>
}
class Volume["frontend/src/lib/types/volume.ts::Volume"] {
  <<interface>>
}
class SwiftContainer["frontend/src/lib/types/objectStorage.ts::SwiftContainer"] {
  <<interface>>
}
class BucketRouteModule["frontend/src/routes/dashboard/object-storage/buckets/+page.svelte"] {
  <<route>>
}

VmCreatePanelModule --> VmCreateStoreModule : creates
VmCreateStoreModule --> ProgressMessage : consumes progress
DroverRouteModule --> K3sListControllerModule : creates
K3sListControllerModule --> K3sCluster : refreshes list
VmCreateStoreModule --> Volume : selects boot/data storage
BucketRouteModule --> SwiftContainer : renders bucket list
```

각 resource workflow의 route/module과 payload 관계는 [workflow index](./workflows/README.md)에서 확인한다.

## 탐색 경로

- [route class diagrams](./src/routes/dashboard/README.md)과 [admin routes](./src/routes/admin/README.md)는 페이지에 선언된 named type을 보여준다.
- [stores](./src/lib/stores/README.md)는 reusable controller/state type을 보여준다.
- [types](./src/lib/types/README.md)는 API payload와 resource contract를 보여준다.
- [workflow diagrams](./workflows/README.md)은 실제 사용자 작업의 순서와 해당 시나리오의 핵심 클래스를 보여준다.

## 상태 소유 규칙

- route는 인증된 project context를 받아 UI와 controller를 조합한다.
- store/controller는 loading, mutation, refresh, toast/progress 상태를 소유한다.
- API client는 bearer token과 project header를 전달하며 `/api/v1` 호출을 수행한다.
- named `types`는 route, component, store 사이에서 공유되는 resource contract다.
