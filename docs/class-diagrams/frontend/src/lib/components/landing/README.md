# `frontend/src/lib/components/landing` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/components/landing`

## 책임
`frontend/src/lib/components/landing`의 책임은 <<interface>>, <<type alias>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 5개 source type과 1개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/components/landing/LandingFigure.svelte`
- `frontend/src/lib/components/landing/LandingPage.svelte`

## 다이어그램 1 — `frontend/src/lib/components/landing/LandingFigure.svelte::Props` … `frontend/src/lib/components/landing/LandingPage.svelte::WorkflowKind`
```mermaid
classDiagram
%% source-type: frontend/src/lib/components/landing/LandingFigure.svelte::Props
class T_frontend_src_lib_components_landing_LandingFigure_svelte_Props_68c248b23f34["Props (frontend/src/lib/components/landing/LandingFigure.svelte)"] {
  <<interface>>
  +class: string | undefined
  +src: string
  +alt: string
  +lazy: boolean | undefined
  +children: Snippet | undefined
}
%% source-type: frontend/src/lib/components/landing/LandingPage.svelte::MethodStep
class T_frontend_src_lib_components_landing_LandingPage_svelte_MethodStep_a646a068bcb0["MethodStep (frontend/src/lib/components/landing/LandingPage.svelte)"] {
  <<type alias>>
  +step: string
  +title: string
  +alt: string
  +src: string | undefined
  +icon: 'observability' | 'reuse' | undefined
}
%% source-type: frontend/src/lib/components/landing/LandingPage.svelte::Props
class T_frontend_src_lib_components_landing_LandingPage_svelte_Props_f4a71d2f9f08["Props (frontend/src/lib/components/landing/LandingPage.svelte)"] {
  <<interface>>
  +siteName: string
  +logoPath: string
  +consoleHref: string
}
%% source-type: frontend/src/lib/components/landing/LandingPage.svelte::WorkflowFilter
class T_frontend_src_lib_components_landing_LandingPage_svelte_WorkflowFilter_cfa2c500cb06["WorkflowFilter (frontend/src/lib/components/landing/LandingPage.svelte)"] {
  <<type alias>>
  +value: 'all' | WorkflowKind
}
%% source-type: frontend/src/lib/components/landing/LandingPage.svelte::WorkflowKind
class T_frontend_src_lib_components_landing_LandingPage_svelte_WorkflowKind_51af3e5a5089["WorkflowKind (frontend/src/lib/components/landing/LandingPage.svelte)"] {
  <<type alias>>
  +value: 'compute' | 'data' | 'ops'
}
T_frontend_src_lib_components_landing_LandingPage_svelte_WorkflowFilter_cfa2c500cb06 --> T_frontend_src_lib_components_landing_LandingPage_svelte_WorkflowKind_51af3e5a5089 : associates
```

### 관계 설명
- `frontend/src/lib/components/landing/LandingPage.svelte::WorkflowFilter --> frontend/src/lib/components/landing/LandingPage.svelte::WorkflowKind` — 근거: `frontend/src/lib/components/landing/LandingPage.svelte::WorkflowFilter.value`; 관계: `associates`.
