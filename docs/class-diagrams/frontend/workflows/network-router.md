---
layout: default
title: Network와 router workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 4
---

# Network와 router workflow

Network와 router 목록 페이지는 route-local state를 소유한다. 생성 성공 뒤 목록을 재조회하고, detail은 URL history와 slide panel로 연다.

## Network 생성 sequence

```mermaid
sequenceDiagram
actor User
participant Route as network page
participant Modal as NetworkCreateModal
participant Mut as apiMut
participant API as /api/v1/networks
participant Table as NetworksTableCard

Route->>API: GET networks + floating IPs + default network
User->>Modal: network form 제출
Modal->>Route: onCreate(body)
Route->>Mut: apiMut(network create)
Mut->>API: POST /api/v1/networks
API-->>Route: created network
Route->>API: GET /api/v1/networks
Route-->>Table: refreshed Network[]
```

## Router 생성 sequence

```mermaid
sequenceDiagram
actor User
participant Route as router page
participant API as /api/v1/networks
participant Modal as RouterCreateModal
participant RouterAPI as /api/v1/routers
participant Grid as RouterCardGrid

Route->>API: GET networks
Route->>Route: filter external networks
User->>Modal: name + external network 제출
Modal->>Route: createRouter(form)
Route->>RouterAPI: POST router body
RouterAPI-->>Route: success
Route->>RouterAPI: GET routers
Route-->>Grid: refreshed Router[]
```

## 시나리오 클래스

```mermaid
classDiagram
class NetworkRouteModule["frontend/src/routes/dashboard/network/networks/+page.svelte"] {
  <<route>>
  +createNetwork()
  +fetchNetworks()
}
class RouterRouteModule["frontend/src/routes/dashboard/network/routers/+page.svelte"] {
  <<route>>
  +createRouter()
  +fetchRouters()
}
class NetworkCreateModalModule["frontend/src/lib/components/dashboard/network/networks/NetworkCreateModal.svelte"] {
  <<component>>
}
class RouterCreateModalModule["frontend/src/lib/components/network/routers/RouterCreateModal.svelte"] {
  <<component>>
}
class Network["frontend/src/lib/types/networks.ts::Network"] {
  <<interface>>
}
class Router["frontend/src/lib/types/networks.ts::Router"] {
  <<interface>>
}
class FloatingIp["frontend/src/lib/types/networks.ts::FloatingIp"] {
  <<interface>>
}
class ApiClientModule["frontend/src/lib/api/client.ts"] {
  <<module>>
}

NetworkRouteModule --> NetworkCreateModalModule : passes onCreate
NetworkRouteModule --> ApiClientModule : list/create/delete
NetworkRouteModule --> Network : renders
NetworkRouteModule --> FloatingIp : refreshes
RouterRouteModule --> RouterCreateModalModule : passes onCreate
RouterRouteModule --> ApiClientModule : list/create
RouterRouteModule --> Network : filters external
RouterRouteModule --> Router : renders
```

## 근거

- `networks/+page.svelte::createNetwork`은 `/api/v1/networks` POST 후 `fetchNetworks()`를 호출한다.
- `routers/+page.svelte::createRouter`는 `/api/v1/routers` POST 후 목록을 다시 읽고, external network 목록은 `/api/v1/networks`에서 필터한다.
