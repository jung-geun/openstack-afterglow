# 차트 라이브러리 비교표

> **작성일**: 2026-05-21  
> **목적**: Afterglow 프론트엔드 차트 영역(raw SVG 자체 구현)을 외부 라이브러리로 교체할 후보 평가  
> **Svelte 버전**: 5.54 (runes 모드)

---

## 배경

현재 Afterglow는 외부 차트 라이브러리 없이 모든 인-앱 차트를 raw SVG + div/Tailwind로 직접 구현하고 있다.  
Grafana iframe 임베드 영역(admin/monitoring/* 9개 페이지 등)은 본 검토 대상에서 제외된다.

### 현재 차트 컴포넌트 현황

| 컴포넌트 | 종류 | 사용처 |
|---|---|---|
| `TimeSeriesChart.svelte` | 라인+영역, 다중 시리즈, range 토글 | admin 4개 페이지 (instances/networks/volumes/file-storage) |
| `MetricsPanel.svelte` | 4~6개 라인 차트 그리드 (CPU/MEM/IO/GPU) | 인스턴스 상세, admin monitoring |
| `ui/Spark.svelte` | 미니 스파크라인 | dashboard 홈, 사용량 페이지 |
| `QuotaDonut.svelte` | 도넛 게이지 (accent/warning/danger) | ResourceDonutsCard (3개), 개별 사용 |
| `ui/Donut.svelte` | 단순 도넛 진행률 | 범용 |
| `LibraryUsageChart.svelte` | 수평 바 (상위 8개) | admin/libraries |
| `dashboard/activity` 24-bin | 수직 바 (시간대별) | dashboard/activity |
| `LibraryDependencyGraph.svelte` | 노드-엣지 다이어그램 | admin/libraries |
| `ui/QuotaBar.svelte` | 수평 진행률 바 | 범용 (라이브러리 대상 제외) |

---

## 평가 기준

| ID | 기준 | 가중치 |
|---|---|---|
| C1 | **Svelte 5 runes 호환성** | 필수 (미지원 → 즉시 탈락) |
| C2 | **번들 크기** (gzip min) | 높음 — dashboard first paint 영향 |
| C3 | **차트 유형 커버리지** | 높음 — 라인/영역/바/도넛/스파크라인 필수 |
| C4 | **디자인 토큰 주입** | 필수 — CSS 변수/prop으로 accent/warning/danger 주입 가능 |
| C5 | **다크 모드** | 필수 — dark scheme 적용 가능 |
| C6 | **인터랙티브 기능** | 중간 — tooltip, zoom, crosshair |
| C7 | **유지보수 활성도** | 중간 — 최근 1년 내 릴리스 |
| C8 | **라이선스** | 필수 — MIT/Apache 2.0 |

---

## 후보 라이브러리 상세 평가

### 1. LayerChart (`layerchart@next`)

**개요**: LayerCake(Svelte-native 그래픽 프레임워크) + D3 위에 구축된 고수준 차트 컴포넌트 라이브러리. `@next` 태그가 Svelte 5 버전.

| 기준 | 평가 | 비고 |
|---|---|---|
| C1 Svelte 5 runes | ✅ 완전 지원 | Svelte 5 전용으로 재작성. runes 네이티브. |
| C2 번들 크기 | ⚠️ 중간-대형 | **실측: ~110 KB gzip** (SvelteKit lazy 청크 1개). d3-interpolate/shape/arc/scale/array + @layerstack/* 전이 deps 포함. dashboard 홈에서 사용 시 주의. |
| C3 차트 유형 | ✅ 전체 커버 | Cartesian(Line/Area/Bar/Scatter), Radial(Pie/Arc/Donut), Hierarchy, Graph(Sankey), Geo, Sparkline 모두 제공 |
| C4 디자인 토큰 | ✅ 자유로운 주입 | 색상을 prop 또는 CSS class로 완전 제어. 기본 팔레트 없음. |
| C5 다크 모드 | ✅ 자연스러운 지원 | CSS 변수 기반 — Tailwind dark: 클래스와 그대로 연동 |
| C6 인터랙션 | ✅ 풍부 | Tooltip snippets, Highlight, Crosshair, Brush zoom, Legend 내장 |
| C7 유지보수 | ✅ 활발 | 2026년 초까지 활발한 릴리스. Svelte 공식 playground에 예제 포함. |
| C8 라이선스 | ✅ MIT | |

**장점**
- Svelte 5 철학(snippet, rune)과 완벽히 정렬
- 색상/스타일 완전 제어 → 기존 디자인 토큰 그대로 유지 (메모리 제약 충족)
- 기존 raw SVG 방식과 동일한 SVG 렌더러 → 점진적 마이그레이션 자연스러움
- `LibraryDependencyGraph` 대체 가능한 Graph 컴포넌트 내장

**단점**
- `@next` 태그이므로 stable 1.x (Svelte 4) 아닌 pre-release 사용 필요
- LayerCake에 D3 의존성 추가됨 (선택적 import로 최소화 가능)
- 문서가 stable보다 적음

**결론**: **1순위 추천**

---

### 2. uPlot

**개요**: 시계열 특화 초경량 Canvas 기반 차트. WebGL/WASM 미사용.

| 기준 | 평가 | 비고 |
|---|---|---|
| C1 Svelte 5 runes | ⚠️ 간접 지원 | `uplot-wrappers` 패키지 제공. Svelte 5 runes 공식 지원 여부 미확인. `$effect` 패턴으로 래핑 가능. |
| C2 번들 크기 | ✅ 최소 | **~50KB gzip** (v1.6.24 기준 47.9KB). 5개 후보 중 최소. |
| C3 차트 유형 | ⚠️ 시계열 전용 | Line/Area/Bar/OHLC. 도넛/스파크라인 없음. |
| C4 디자인 토큰 | ✅ 가능 | 색상 option 객체로 완전 제어 |
| C5 다크 모드 | ✅ 가능 | CSS + option 조합으로 처리 |
| C6 인터랙션 | ✅ 최고 수준 | tooltip, crosshair, zoom/pan, 60fps 스트리밍 가능 |
| C7 유지보수 | ✅ 유지 | GitHub 지속 관리 중 |
| C8 라이선스 | ✅ MIT | |

**성능 참고**: 3,600 포인트 60fps 업데이트 시 CPU 10%, RAM 12.3MB. Chart.js 동 조건에서 40%/77MB.

**장점**
- MetricsPanel (4~6개 시계열, 고빈도 업데이트) 에 이상적
- 번들 크기가 가장 작음

**단점**
- 시계열 라인/바 외 차트 유형 없음 → 도넛/스파크라인은 여전히 자체 구현 필요
- Svelte 5 runes 공식 래퍼 성숙도 미확인
- Canvas 기반 → SVG 스타일 제어와 패러다임 다름

**결론**: **MetricsPanel 단독 적용 시 2순위 보조 후보**. 전사 라이브러리로는 부적합.

---

### 3. Apache ECharts (`echarts` + `svelte-echarts`)

**개요**: Apache 재단 관리 범용 차트 라이브러리. `echarts/core` tree-shaking 지원.

| 기준 | 평가 | 비고 |
|---|---|---|
| C1 Svelte 5 runes | ⚠️ 래퍼 의존 | `svelte-echarts` (bherbruck) 래퍼. Svelte 5 runes 지원 여부 확인 필요. |
| C2 번들 크기 | ❌ 대형 | 전체 ~1MB. tree-shaking으로 pie+title = **~135KB gzip**. 최소 구성도 100KB+ 예상. |
| C3 차트 유형 | ✅ 최다 | Line/Bar/Pie/Scatter/Heatmap/Graph(force layout)/Sankey 등 전 유형 |
| C4 디자인 토큰 | ✅ 가능 | theme 객체로 색상 완전 제어 |
| C5 다크 모드 | ✅ dark theme 내장 | |
| C6 인터랙션 | ✅ 풍부 | tooltip, zoom, brush, legend, datazoom |
| C7 유지보수 | ✅ 매우 활발 | Apache 재단 관리, v6.0 출시 |
| C8 라이선스 | ✅ Apache 2.0 | |

**장점**
- `LibraryDependencyGraph` force layout 교체 가능
- 모든 차트 유형을 단일 라이브러리로 커버

**단점**
- tree-shaking 후에도 100KB+ — dashboard 페이지 first paint에 부담
- Svelte 5 래퍼 성숙도 미확인
- Canvas 기반 (SVG 모드 옵션 있지만 추가 설정 필요)

**결론**: **의존성 그래프 force layout이 필수 요구사항이 될 경우에만 재검토**

---

### 4. Chart.js + `svelte-chartjs`

**개요**: 가장 널리 쓰이는 Canvas 기반 차트 라이브러리. `svelte-chartjs` 래퍼는 2026-03 업데이트됨.

| 기준 | 평가 | 비고 |
|---|---|---|
| C1 Svelte 5 runes | ✅ 가능 | `$effect` rune 패턴으로 사용. Svelte 공식 playground 예제 존재. |
| C2 번들 크기 | ✅ 중간 | Chart.js gzip **~60KB**. 합리적. |
| C3 차트 유형 | ✅ 대부분 커버 | Line/Bar/Radar/Doughnut/Pie/Bubble/Scatter. 도넛 포함. |
| C4 디자인 토큰 | ✅ 가능 | `options.plugins.colors` 비활성화 후 `borderColor`/`backgroundColor` 직접 지정 |
| C5 다크 모드 | ⚠️ 수동 처리 | 기본값 없음. `color`/`borderColor` 직접 분기 필요. |
| C6 인터랙션 | ✅ 충분 | tooltip, legend, zoom (plugin 별도) |
| C7 유지보수 | ✅ 활발 | 메이저 v4 유지 중 |
| C8 라이선스 | ✅ MIT | |

**장점**
- 가장 많은 레퍼런스와 예제
- svelte-chartjs 최근 업데이트 (2026-03)
- 적당한 번들 크기

**단점**
- Canvas 기반 → SVG 세부 스타일 제어 어려움
- 다크 모드 처리가 번거로움
- 스파크라인 용도로는 과함 (전체 Chart.js 로드 필요)
- LayerChart 대비 Svelte 5 통합 자연스럽지 않음

**결론**: **LayerChart 대비 Svelte 5 친화성 낮고 다크 모드 처리 번거로움. 3순위.**

---

### 5. ApexCharts (`apexcharts` + `svelte-chart-apex`)

**개요**: 풍부한 기능의 SVG 기반 차트. 그러나 번들 크기가 치명적.

| 기준 | 평가 | 비고 |
|---|---|---|
| C1 Svelte 5 runes | ⚠️ 래퍼 필요 | `svelte-chart-apex` (hyunbinseo) Svelte 5 wrapper 존재 |
| C2 번들 크기 | ❌ **탈락** | **>400KB gzip** (GitHub issue #157 확인). tree-shaking 미지원. |
| C3~C8 | — | 번들 크기 이슈로 평가 중단 |

**결론**: **즉시 탈락. 번들 크기가 dashboard 전체 JS보다 클 수 있음.**

---

## 종합 비교 매트릭스

| | C1 Svelte5 | C2 번들 | C3 유형 | C4 토큰 | C5 다크 | C6 인터랙션 | C7 유지보수 | C8 라이선스 | **종합** |
|---|---|---|---|---|---|---|---|---|---|
| **LayerChart** | ✅ | ⚠️ **~110KB gzip** (실측) | ✅ 전체 | ✅ 완전 자유 | ✅ | ✅ 풍부 | ✅ | ✅ MIT | ⭐⭐⭐⭐ (admin용 OK, dashboard 홈 주의) |
| **uPlot** | ⚠️ | ✅ ~50KB | ⚠️ 시계열만 | ✅ | ✅ | ✅ 최고 | ✅ | ✅ MIT | ⭐⭐⭐ (시계열 전용) |
| **ECharts** | ⚠️ | ❌ ~135KB+ | ✅ 최다 | ✅ | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐ (그래프 필요시) |
| **Chart.js** | ✅ | ✅ ~60KB | ✅ 대부분 | ✅ | ⚠️ | ✅ | ✅ | ✅ MIT | ⭐⭐⭐ |
| **ApexCharts** | ⚠️ | ❌ **>400KB** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ 탈락 |

---

## PoC 실측 결과

> **테스트**: `TimeSeriesChart.poc.svelte` + `QuotaDonut.poc.svelte` 를 admin/instances 페이지에 포함시켜 `vite build` 측정

| 지표 | 값 |
|---|---|
| 기준선 (라이브러리 없음) | **288,451 bytes gzip** (전체 청크 합계) |
| LayerChart 포함 후 | **447,405 bytes gzip** |
| **증가량** | **+158,954 bytes gzip (~155 KB)** |
| LayerChart 단독 청크 | **110,460 bytes gzip** (365 KB raw) |
| 로딩 방식 | SvelteKit 코드 분할 — 해당 라우트 최초 방문 시에만 로딩 |

### 증가 원인 분석

LayerChart 자체보다 **전이 의존성**이 대부분의 크기를 차지함:

- `d3-scale`, `d3-array` — 스케일 계산
- `d3-shape` — Area/Spline 경로 생성
- `d3-arc` — Arc/Donut 경로
- `d3-interpolate` — 애니메이션(motion)
- `@layerstack/utils`, `@layerstack/tailwind`, `@layerstack/svelte-actions` — LayerChart 내부 유틸

### 결론: 라우트별 분리 전략 채택

| 사용처 | 권장 방향 |
|---|---|
| Admin 페이지 (`/admin/*`) | **LayerChart 도입 OK** — 관리자 전용, 지연 로딩, 155 KB 허용 가능 |
| Dashboard 홈 Spark 카드 | **raw SVG 유지** — 홈 초기 로딩에 155 KB 추가 불가 |
| MetricsPanel (인스턴스 상세) | **LayerChart 1차 도입 → 성능 불량 시 uPlot 교체** |

---

## 권장 결론

### 주력 라이브러리: **LayerChart (`layerchart@next`)** — admin 영역 한정

- Svelte 5 runes 네이티브 — 코드베이스와 완전 정렬
- 색상/스타일 완전 자유 — 기존 디자인 토큰 그대로 유지
- SVG 기반 — 기존 raw SVG 코드와 동일한 패러다임, 점진적 마이그레이션 용이
- 라인/영역/바/도넛/스파크라인/그래프 모두 단일 라이브러리로 커버
- **단, 실측 110 KB gzip 청크로 인해 dashboard 홈 등 초기 로딩 경로에는 사용 금지**

### 유지 (라이브러리 미도입): **`ui/Spark.svelte`**

- dashboard 홈 초기 로딩 경로 — raw SVG 그대로 유지
- 이미 가볍고(SVG `<path>` 10줄), 인터랙션 불필요
- LayerChart 도입 시 110 KB가 dashboard 홈에 추가되므로 분리 필수

### 보조 고려 (선택): **uPlot**

- `MetricsPanel`에만 국한 적용 시 의미 있음 (고빈도 실시간 시계열, 50 KB gzip)
- 전사 라이브러리로는 채택 불가 (도넛/스파크라인 미지원)
- LayerChart로 MetricsPanel 구현 후 성능이 문제될 경우 단계적 교체 검토

### 탈락

| 라이브러리 | 탈락 사유 |
|---|---|
| ApexCharts | 번들 >400KB gzip — 즉시 탈락 |
| ECharts | tree-shaking 후에도 135KB+. 의존성 그래프 force layout이 필수화되면 재검토. |
| Chart.js | LayerChart 대비 Svelte 5 친화성 낮고 다크 모드 처리 번거로움 |

---

## 참고 링크

- LayerChart: https://www.layerchart.com/changelog (Svelte 5 릴리스)
- uPlot: https://github.com/leeoniya/uplot
- ECharts tree-shaking: https://apache.github.io/echarts-handbook/en/basics/import/
- svelte-chartjs npm: https://www.npmjs.com/package/svelte-chartjs
- ApexCharts bundle issue: https://github.com/galkatz373/svelte-apexcharts/issues/157
