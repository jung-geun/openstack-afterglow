# `frontend/src` 클래스 다이어그램

**대상 경로:** `frontend/src`

## 책임
`frontend/src`의 책임은 <<interface>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 2개 source type과 2개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/app.d.ts`
- `frontend/src/lib/constants/flavorSpecTemplates.ts`

## 다이어그램 1 — `frontend/src/app.d.ts::App.Locals` … `frontend/src/lib/types/siteConfig.ts::PublicSiteConfig`
```mermaid
classDiagram
%% source-type: frontend/src/app.d.ts::App.Locals
class T_frontend_src_app_d_ts_App_Locals_8217210dd47a["App.Locals (frontend/src/app.d.ts)"] {
  <<interface>>
  +mockup: MockupSession
  +siteConfig: PublicSiteConfig
}
%% source-type: frontend/src/lib/constants/flavorSpecTemplates.ts::FlavorSpecTemplate
class T_frontend_src_lib_constants_flavorSpecTemplates_ts_FlavorSpecTemplate_90ed4ec089e9["FlavorSpecTemplate (frontend/src/lib/constants/flavorSpecTemplates.ts)"] {
  <<interface>>
  +key: string
  +category: string
  +label: string
  +description: string
  +valueType: 'enum' | 'number' | 'text' | 'gpu_alias'
  +options: Array~string~ | undefined
  +placeholder: string | undefined
  +defaultValue: string | undefined
}
%% external-type: frontend/src/lib/mockup/contracts.ts::MockupSession
class T_frontend_src_lib_mockup_contracts_ts_MockupSession_2bd773b649c6["MockupSession (lib/mockup/contracts.ts)"] {
  <<external>>
}
%% external-type: frontend/src/lib/types/siteConfig.ts::PublicSiteConfig
class T_frontend_src_lib_types_siteConfig_ts_PublicSiteConfig_46b7a58fa52a["PublicSiteConfig (lib/types/siteConfig.ts)"] {
  <<external>>
}
T_frontend_src_app_d_ts_App_Locals_8217210dd47a --> T_frontend_src_lib_mockup_contracts_ts_MockupSession_2bd773b649c6 : associates
T_frontend_src_app_d_ts_App_Locals_8217210dd47a --> T_frontend_src_lib_types_siteConfig_ts_PublicSiteConfig_46b7a58fa52a : associates
```

### 관계 설명
- `frontend/src/app.d.ts::App.Locals --> frontend/src/lib/mockup/contracts.ts::MockupSession` — 근거: `frontend/src/app.d.ts::App.Locals.mockup`; 관계: `associates`.
- `frontend/src/app.d.ts::App.Locals --> frontend/src/lib/types/siteConfig.ts::PublicSiteConfig` — 근거: `frontend/src/app.d.ts::App.Locals.siteConfig`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `Array~string~` | `string[]` |
