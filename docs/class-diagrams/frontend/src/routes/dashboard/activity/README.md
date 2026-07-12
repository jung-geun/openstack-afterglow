# `frontend/src/routes/dashboard/activity` 클래스 다이어그램

**대상 경로:** `frontend/src/routes/dashboard/activity`

## 책임
`frontend/src/routes/dashboard/activity`의 책임은 <<interface>>, <<type alias>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 4개 source type과 2개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/routes/dashboard/activity/+page.svelte`

## 다이어그램 1 — `frontend/src/routes/dashboard/activity/+page.svelte::ActionBadgeStyle` … `frontend/src/routes/dashboard/activity/+page.svelte::RecentAction`
```mermaid
classDiagram
%% source-type: frontend/src/routes/dashboard/activity/+page.svelte::ActionBadgeStyle
class T_frontend_src_routes_dashboard_activity_page_svelte_ActionBadgeStyle_f5b22fb4716e["ActionBadgeStyle (frontend/src/routes/dashboard/activity/+page.svelte)"] {
  <<type alias>>
  +bg: string
  +text: string
}
%% source-type: frontend/src/routes/dashboard/activity/+page.svelte::ActivityData
class T_frontend_src_routes_dashboard_activity_page_svelte_ActivityData_5c8873fc1017["ActivityData (frontend/src/routes/dashboard/activity/+page.svelte)"] {
  <<interface>>
  +range: string
  +kpi: KPI
  +hour_distribution: Array~number~
  +recent_actions: Array~RecentAction~
  +db_status: 'ok' | 'unavailable' | undefined
}
%% source-type: frontend/src/routes/dashboard/activity/+page.svelte::KPI
class T_frontend_src_routes_dashboard_activity_page_svelte_KPI_4563b27b394a["KPI (frontend/src/routes/dashboard/activity/+page.svelte)"] {
  <<interface>>
  +total: number
  +success: number
  +failed: number
  +last_24h: number
  +unique_users: number
}
%% source-type: frontend/src/routes/dashboard/activity/+page.svelte::RecentAction
class T_frontend_src_routes_dashboard_activity_page_svelte_RecentAction_98951b2e93f1["RecentAction (frontend/src/routes/dashboard/activity/+page.svelte)"] {
  <<interface>>
  +id: number
  +created_at: string
  +action: string
  +resource_type: string
  +resource_name: string
  +status: string
  +user_id: string
  +error_message: string | null
}
T_frontend_src_routes_dashboard_activity_page_svelte_ActivityData_5c8873fc1017 --> T_frontend_src_routes_dashboard_activity_page_svelte_KPI_4563b27b394a : associates
T_frontend_src_routes_dashboard_activity_page_svelte_ActivityData_5c8873fc1017 --> T_frontend_src_routes_dashboard_activity_page_svelte_RecentAction_98951b2e93f1 : associates
```

### 관계 설명
- `frontend/src/routes/dashboard/activity/+page.svelte::ActivityData --> frontend/src/routes/dashboard/activity/+page.svelte::KPI` — 근거: `frontend/src/routes/dashboard/activity/+page.svelte::ActivityData.kpi`; 관계: `associates`.
- `frontend/src/routes/dashboard/activity/+page.svelte::ActivityData --> frontend/src/routes/dashboard/activity/+page.svelte::RecentAction` — 근거: `frontend/src/routes/dashboard/activity/+page.svelte::ActivityData.recent_actions`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `Array~number~` | `number[]` |
| `Array~RecentAction~` | `RecentAction[]` |
