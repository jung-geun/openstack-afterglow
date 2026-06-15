## Phase 54 — 차트 라이브러리 도입 검토

**목표**: 현재 raw SVG 자체 구현 차트들을 외부 라이브러리로 교체할지 평가. 비교표 + PoC + 권장 로드맵 산출.

### Phase 54a — 라이브러리 비교표 작성

- [x] 5개 후보(LayerChart, uPlot, ECharts, Chart.js, ApexCharts) 평가 기준 매트릭스 작성
- [x] `frontend/docs/chart-library-comparison.md` 산출

### Phase 54b — PoC 구현

- [x] 최종 후보 1~2개 선정 후 `TimeSeriesChart.poc.svelte`, `QuotaDonut.poc.svelte` 작성
- [x] 번들 크기 전후 비교 (`vite build`) — 기준선 288 KB → LayerChart 포함 447 KB (+155 KB gzip)

### Phase 54c — 권장 로드맵 작성

- [x] 도입 추천/비추천 결정 + 마이그레이션 우선순위
- [x] `frontend/docs/chart-library-roadmap.md` 산출

