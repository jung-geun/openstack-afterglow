# `frontend/src/lib/config` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/config`

## 책임
`frontend/src/lib/config`의 책임은 <<interface>>, <<type alias>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 6개 source type과 4개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/config/brandAssets.ts`
- `frontend/src/lib/config/nav.ts`
- `frontend/src/lib/config/routes.ts`
- `frontend/src/lib/config/site.ts`
- `frontend/src/lib/config/statusColors.ts`

## 다이어그램 1 — `frontend/src/lib/config/brandAssets.ts::ResolvedBrandTheme` … `frontend/src/lib/types/siteConfig.ts::PublicSiteConfig`
```mermaid
classDiagram
%% source-type: frontend/src/lib/config/brandAssets.ts::ResolvedBrandTheme
class T_frontend_src_lib_config_brandAssets_ts_ResolvedBrandTheme_6040034ede58["ResolvedBrandTheme (frontend/src/lib/config/brandAssets.ts)"] {
  <<type alias>>
  +value: 'dark' | 'light'
}
%% source-type: frontend/src/lib/config/nav.ts::NavItem
class T_frontend_src_lib_config_nav_ts_NavItem_42f7d9335ad4["NavItem (frontend/src/lib/config/nav.ts)"] {
  <<interface>>
  +label: string
  +href: string
  +service: string | null
  +beta: keyof BetaFeatures | undefined
}
%% source-type: frontend/src/lib/config/nav.ts::NavSection
class T_frontend_src_lib_config_nav_ts_NavSection_93d54db6c942["NavSection (frontend/src/lib/config/nav.ts)"] {
  <<interface>>
  +label: string
  +prefix: string
  +extraPrefixes: Array~string~ | undefined
  +icon: string
  +service: string | null | undefined
  +beta: keyof BetaFeatures | undefined
  +items: Array~NavItem~
}
%% source-type: frontend/src/lib/config/routes.ts::BreadcrumbResult
class T_frontend_src_lib_config_routes_ts_BreadcrumbResult_f2166b638782["BreadcrumbResult (frontend/src/lib/config/routes.ts)"] {
  <<interface>>
  +breadcrumb: string
  +title: string
}
%% source-type: frontend/src/lib/config/site.ts::SiteConfig
class T_frontend_src_lib_config_site_ts_SiteConfig_a81334aa5d3a["SiteConfig (frontend/src/lib/config/site.ts)"] {
  <<type alias>>
  +value: PublicSiteConfig
}
%% source-type: frontend/src/lib/config/statusColors.ts::StatusStyle
class T_frontend_src_lib_config_statusColors_ts_StatusStyle_f990acde6de7["StatusStyle (frontend/src/lib/config/statusColors.ts)"] {
  <<interface>>
  +tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  +pulse: boolean | undefined
  +label: string | undefined
}
%% external-type: frontend/src/lib/stores/betaFeatures.ts::BetaFeatures
class T_frontend_src_lib_stores_betaFeatures_ts_BetaFeatures_c71436438d77["BetaFeatures (../stores/betaFeatures.ts)"] {
  <<external>>
}
%% external-type: frontend/src/lib/types/siteConfig.ts::PublicSiteConfig
class T_frontend_src_lib_types_siteConfig_ts_PublicSiteConfig_46b7a58fa52a["PublicSiteConfig (../types/siteConfig.ts)"] {
  <<external>>
}
T_frontend_src_lib_config_nav_ts_NavItem_42f7d9335ad4 --> T_frontend_src_lib_stores_betaFeatures_ts_BetaFeatures_c71436438d77 : associates
T_frontend_src_lib_config_nav_ts_NavSection_93d54db6c942 --> T_frontend_src_lib_config_nav_ts_NavItem_42f7d9335ad4 : associates
T_frontend_src_lib_config_nav_ts_NavSection_93d54db6c942 --> T_frontend_src_lib_stores_betaFeatures_ts_BetaFeatures_c71436438d77 : associates
T_frontend_src_lib_config_site_ts_SiteConfig_a81334aa5d3a --> T_frontend_src_lib_types_siteConfig_ts_PublicSiteConfig_46b7a58fa52a : associates
```

### 관계 설명
- `frontend/src/lib/config/nav.ts::NavItem --> frontend/src/lib/stores/betaFeatures.ts::BetaFeatures` — 근거: `frontend/src/lib/config/nav.ts::NavItem.beta`; 관계: `associates`.
- `frontend/src/lib/config/nav.ts::NavSection --> frontend/src/lib/config/nav.ts::NavItem` — 근거: `frontend/src/lib/config/nav.ts::NavSection.items`; 관계: `associates`.
- `frontend/src/lib/config/nav.ts::NavSection --> frontend/src/lib/stores/betaFeatures.ts::BetaFeatures` — 근거: `frontend/src/lib/config/nav.ts::NavSection.beta`; 관계: `associates`.
- `frontend/src/lib/config/site.ts::SiteConfig --> frontend/src/lib/types/siteConfig.ts::PublicSiteConfig` — 근거: `frontend/src/lib/config/site.ts::SiteConfig.value`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `Array~string~` | `string[]` |
| `Array~NavItem~` | `NavItem[]` |
