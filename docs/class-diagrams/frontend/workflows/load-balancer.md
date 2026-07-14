---
layout: default
title: Load balancer 생성 workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 3
---

# Load balancer 생성 workflow

**진입점:** `frontend/src/routes/dashboard/network/loadbalancers/new/+page.svelte`가 network 선택과 VIP subnet 선택을 수행한 뒤 load balancer를 생성하고 detail route로 이동한다.

## Sequence

```mermaid
sequenceDiagram
actor User
participant Route as LB new page
participant API as api client
participant Networks as /api/v1/networks
participant LB as /api/v1/loadbalancers
participant Detail as LB detail route

Route->>Networks: GET network 목록
Networks-->>Route: Network[]
User->>Route: VIP network 선택
Route->>Networks: GET /networks/{id}
Networks-->>Route: subnet_details
User->>Route: name + VIP subnet 제출
Route->>LB: POST name, vip_subnet_id, description
LB-->>Route: { id }
Route->>Detail: goto(/dashboard/network/loadbalancers/{id})
```

## 시나리오 클래스

```mermaid
classDiagram
class LoadBalancerNewRouteModule["frontend/src/routes/dashboard/network/loadbalancers/new/+page.svelte"] {
  <<route>>
  +loadNetworks()
  +onNetworkChange()
  +createLb()
}
class ApiClientModule["frontend/src/lib/api/client.ts"] {
  <<module>>
}
class Network["frontend/src/lib/types/networks.ts::Network"] {
  <<interface>>
}
class SubnetDetail["frontend/src/lib/types/networks.ts::SubnetDetail"] {
  <<interface>>
}
class LoadBalancerEndpoint["/api/v1/loadbalancers"] {
  <<HTTP endpoint>>
}

LoadBalancerNewRouteModule --> ApiClientModule : calls
LoadBalancerNewRouteModule --> Network : selects VIP network
Network --> SubnetDetail : exposes subnet_details
LoadBalancerNewRouteModule --> LoadBalancerEndpoint : POST
```

## 근거

- `loadbalancers/new/+page.svelte::loadNetworks`는 `/api/v1/networks`를 조회한다.
- `onNetworkChange`는 선택한 network detail에서 `subnet_details`를 읽는다.
- `createLb`는 `/api/v1/loadbalancers` POST 성공 후 detail route로 이동한다.
