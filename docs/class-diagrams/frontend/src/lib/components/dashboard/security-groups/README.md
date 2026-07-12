# `frontend/src/lib/components/dashboard/security-groups` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/components/dashboard/security-groups`

## 책임
`frontend/src/lib/components/dashboard/security-groups`의 책임은 <<interface>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 3개 source type과 1개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte`
- `frontend/src/lib/components/dashboard/security-groups/SecurityGroupRuleTable.svelte`

## 다이어그램 1 — `frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroup` … `frontend/src/lib/components/dashboard/security-groups/SecurityGroupRuleTable.svelte::SecurityGroupRule`
```mermaid
classDiagram
%% source-type: frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroup
class T_frontend_src_lib_components_dashboard_security_groups_SecurityGroupCard_svelte_SecurityGroup_9e87aff2dcfe["SecurityGroup (frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte)"] {
  <<interface>>
  +id: string
  +name: string
  +description: string
  +rules: Array~SecurityGroupRule~
}
%% source-type: frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroupRule
class T_frontend_src_lib_components_dashboard_security_groups_SecurityGroupCard_svelte_SecurityGroupRule_71900856a87d["SecurityGroupRule (frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte)"] {
  <<interface>>
  +id: string
  +direction: string
  +protocol: string | null
  +port_range_min: number | null
  +port_range_max: number | null
  +remote_ip_prefix: string | null
  +ethertype: string
}
%% source-type: frontend/src/lib/components/dashboard/security-groups/SecurityGroupRuleTable.svelte::SecurityGroupRule
class T_frontend_src_lib_components_dashboard_security_groups_SecurityGroupRuleTable_svelte_SecurityGroupRule_5c6f9cafbc19["SecurityGroupRule (frontend/src/lib/components/dashboard/security-groups/SecurityGroupRuleTable.svelte)"] {
  <<interface>>
  +id: string
  +direction: string
  +protocol: string | null
  +port_range_min: number | null
  +port_range_max: number | null
  +remote_ip_prefix: string | null
  +ethertype: string
}
T_frontend_src_lib_components_dashboard_security_groups_SecurityGroupCard_svelte_SecurityGroup_9e87aff2dcfe --> T_frontend_src_lib_components_dashboard_security_groups_SecurityGroupCard_svelte_SecurityGroupRule_71900856a87d : associates
```

### 관계 설명
- `frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroup --> frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroupRule` — 근거: `frontend/src/lib/components/dashboard/security-groups/SecurityGroupCard.svelte::SecurityGroup.rules`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `Array~SecurityGroupRule~` | `SecurityGroupRule[]` |
