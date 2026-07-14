# `frontend/src/lib/components/loadbalancer` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/components/loadbalancer`

## 책임
`frontend/src/lib/components/loadbalancer`의 책임은 <<interface>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 3개 source type과 1개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/components/loadbalancer/LoadBalancerDetailHeader.svelte`
- `frontend/src/lib/components/loadbalancer/LoadBalancerErrorTree.svelte`
- `frontend/src/lib/components/loadbalancer/PoolMembersPanel.svelte`

## 다이어그램 1 — `frontend/src/lib/components/loadbalancer/LoadBalancerDetailHeader.svelte::Props` … `frontend/src/lib/types/loadbalancer.ts::LbStatusNode`
```mermaid
classDiagram
%% source-type: frontend/src/lib/components/loadbalancer/LoadBalancerDetailHeader.svelte::Props
class T_frontend_src_lib_components_loadbalancer_LoadBalancerDetailHeader_svelte_Props_dfb0b7daaaef["Props (frontend/src/lib/components/loadbalancer/LoadBalancerDetailHeader.svelte)"] {
  <<interface>>
  +ar: object
  +onClose: Callable~; returns void~ | undefined
}
%% source-type: frontend/src/lib/components/loadbalancer/LoadBalancerErrorTree.svelte::Props
class T_frontend_src_lib_components_loadbalancer_LoadBalancerErrorTree_svelte_Props_3aba40166ff3["Props (frontend/src/lib/components/loadbalancer/LoadBalancerErrorTree.svelte)"] {
  <<interface>>
  +node: LbStatusNode | null | undefined
  +depth: number | undefined
}
%% source-type: frontend/src/lib/components/loadbalancer/PoolMembersPanel.svelte::Props
class T_frontend_src_lib_components_loadbalancer_PoolMembersPanel_svelte_Props_9cb9cf00ddb9["Props (frontend/src/lib/components/loadbalancer/PoolMembersPanel.svelte)"] {
  <<interface>>
  +poolId: string
}
%% external-type: frontend/src/lib/types/loadbalancer.ts::LbStatusNode
class T_frontend_src_lib_types_loadbalancer_ts_LbStatusNode_41ce4c95b972["LbStatusNode (../../types/loadbalancer.ts)"] {
  <<external>>
}
T_frontend_src_lib_components_loadbalancer_LoadBalancerErrorTree_svelte_Props_3aba40166ff3 --> T_frontend_src_lib_types_loadbalancer_ts_LbStatusNode_41ce4c95b972 : associates
```

### 관계 설명
- `frontend/src/lib/components/loadbalancer/LoadBalancerErrorTree.svelte::Props --> frontend/src/lib/types/loadbalancer.ts::LbStatusNode` — 근거: `frontend/src/lib/components/loadbalancer/LoadBalancerErrorTree.svelte::Props.node`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `object` | `{ active: boolean; intervalSeconds: number; intervalOptions: number[] }` |
| `Callable~; returns void~` | `() => void` |
