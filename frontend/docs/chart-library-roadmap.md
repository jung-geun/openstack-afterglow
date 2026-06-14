# 차트 라이브러리 도입 권장 로드맵

> **작성일**: 2026-05-21  
> **의사결정**: LayerChart (`layerchart@next`) 도입 권장  
> **상세 비교 근거**: [chart-library-comparison.md](./chart-library-comparison.md)

---

## 결론 요약

**LayerChart (`layerchart@next`) 도입 권장.**

현재 raw SVG 자체 구현 방식은 새 차트 유형 추가 비용이 높고, hover tooltip/zoom 등 인터랙션이 부재한다. LayerChart는 Svelte 5 runes 네이티브이며, CSS 변수를 통해 기존 디자인 토큰(accent/warning/danger)을 그대로 유지할 수 있고, SVG 기반으로 기존 코드 패러다임과 일치한다.

**변경 없는 영역**:
- Grafana iframe (`admin/monitoring/*`, `dashboard/observability` 등) — 전혀 건드리지 않음
- `ui/QuotaBar.svelte`, `ProgressBar.svelte` — 단순 div 진행률, 라이브러리 불필요
- `wizard/VmDeployProgress.svelte` — 동일

---

## 설치

```bash
cd frontend
npm install layerchart@next
# D3 스케일 유틸 (LayerChart 내부 peer dep)
npm install d3-scale d3-array
```

> `package.json` dependencies에 추가. devDependency 아님 (런타임 필요).

---

## 마이그레이션 우선순위

재사용 횟수와 인터랙션 개선 효과 기준으로 순위를 정한다.

### 1순위 — `TimeSeriesChart.svelte` (4개 admin 페이지에서 재사용)

**현재**: raw SVG polyline + polygon. range 토글(1d/2d/7d/30d). 보조 점선 시리즈.  
**교체 후**: LayerChart `<Chart>` + `<Area>` + `<Axis>` + `<Tooltip>`. range 토글 유지.  
**기대 효과**: hover tooltip, 반응형 폭, 다중 시리즈 legend.

사용처:
- `routes/admin/instances/+page.svelte`
- `components/admin/file-storage/AdminFileStorageTimeseries.svelte`
- `components/admin/networks/AdminNetworkTimeseries.svelte`
- `components/admin/volumes/AdminVolumeTimeseries.svelte`

### 2순위 — `QuotaDonut.svelte` + `ui/Donut.svelte`

**현재**: SVG `<circle>` stroke-dasharray.  
**교체 후**: LayerChart `<Arc>` / `<Pie>` 컴포넌트. gradient + accent/warning/danger 단계 유지.  
**기대 효과**: hover tooltip (used/limit 표시), 애니메이션.

사용처:
- `components/admin/overview/ResourceDonutsCard.svelte` (3개)
- 범용 `ui/Donut.svelte` 사용처 전체

### 3순위 — `ui/Spark.svelte`

**현재**: SVG `<path>` mini 라인+영역.  
**교체 후**: LayerChart `<Sparkline>` 컴포넌트 (또는 그대로 유지 — 이미 충분히 가벼움).  
**기대 효과**: hover 시 포인트 값 표시.

사용처:
- `routes/dashboard/+page.svelte` (3개)
- `routes/dashboard/usage/+page.svelte` (4개)

### 4순위 — `LibraryUsageChart.svelte` + dashboard/activity 24-bin 바

**현재**: div+Tailwind 높이 비례.  
**교체 후**: LayerChart `<Bar>`.  
**기대 효과**: hover tooltip, 정확한 값 표시, 반응형.

### 제외 — `ui/Spark.svelte`

**결정**: raw SVG 유지. 이미 SVG `<path>` 10줄로 완성된 컴포넌트이며, LayerChart로 교체해도 tooltip/zoom 등 실질적 기능 개선이 없어 110 KB 비용 대비 효용이 없음.

### 5순위 — `MetricsPanel.svelte`

**현재**: raw SVG 480×120 polyline. 4~6개 라인 차트 그리드.  
**1차 시도**: LayerChart로 교체 후 성능 측정.  
**성능 부족 시**: uPlot로 단독 교체 검토 (3,600pt 60fps 업데이트 기준 CPU 10%).

### 보류 — `LibraryDependencyGraph.svelte`

노드-엣지 다이어그램은 force layout이 필요. LayerChart의 Graph(Sankey) 컴포넌트는 force layout이 아니므로 현재 raw SVG 유지. ECharts force graph가 필요해지면 별도 검토.

---

## 점진적 도입 전략

기존 컴포넌트를 **즉시 삭제하지 않는다**. 다음 순서로 진행:

```
Phase 54b-1: TimeSeriesChart.svelte → LayerChart PoC 작성 및 비교 검증
Phase 54b-2: 검증 통과 시 기존 파일 교체 (svelte-check 통과, 시각 동등성 확인)
Phase 54c  : QuotaDonut 교체
Phase 54d  : Spark 교체
Phase 54e  : 바 차트 교체
Phase 54f  : MetricsPanel 교체 (성능 벤치마크 선행)
```

각 단계마다:
1. `*.poc.svelte` 신규 파일 작성
2. dev 서버에서 `/browse`로 시각 동등성 확인
3. dark mode / light mode 양쪽 확인
4. `npm run check` (svelte-check) 통과
5. 기존 파일 교체 후 PoC 파일 삭제
6. `npm run build` 번들 크기 측정

---

## 디자인 토큰 매핑 가이드

LayerChart 컴포넌트 색상은 prop 또는 CSS class로 완전 제어된다.  
**기존 Tailwind/CSS 변수 그대로 사용**:

```svelte
<!-- TimeSeriesChart 교체 예시 -->
<Chart data={points} x="timestamp" y="value">
  <Area class="fill-accent/20 stroke-accent" />
  <Axis placement="bottom" />
  <Tooltip />
</Chart>
```

```svelte
<!-- QuotaDonut 교체 예시 (used/limit 비율에 따라 클래스 분기) -->
<script>
  const colorClass = $derived(
    ratio > 0.9 ? 'stroke-danger' :
    ratio > 0.7 ? 'stroke-warning' :
    'stroke-accent'
  );
</script>
<Chart data={[{ value: used }, { value: limit - used }]}>
  <Arc class={colorClass} />
</Chart>
```

**색상 추가 금지**: 새 색상 팔레트를 도입하지 않는다. 기존 `accent/warning/danger/text-*` 토큰만 사용.

---

## 번들 크기 실측값

> PoC (`TimeSeriesChart.poc.svelte` + `QuotaDonut.poc.svelte`) 기준 실제 측정 (2026-05-21)

| 상태 | gzip 크기 |
|---|---|
| 기준선 (라이브러리 없음) | 288,451 bytes |
| LayerChart 포함 후 | 447,405 bytes |
| **총 증가량** | **+~155 KB gzip** |
| LayerChart 단독 lazy 청크 | **~110 KB gzip** (전이 D3 deps 포함) |

**핵심 시사점**:
- LayerChart 청크(110 KB)는 해당 라우트 최초 방문 시에만 로딩됨 (SvelteKit 코드 분할)
- Admin/Dashboard 모두 기술적으로는 도입 가능
- `ui/Spark.svelte`는 **교체 불필요** — SVG 10줄로 이미 완성된 컴포넌트, 110 KB를 내고 얻을 기능 개선이 없음 (tooltip/zoom 불필요)

---

## 위험 요소 및 완화

| 위험 | 확률 | 완화 |
|---|---|---|
| `layerchart@next` pre-release 불안정 | 낮음 | 공식 Svelte playground에 예제 존재. 2026년 초까지 활발한 릴리스. |
| D3 peer dep 번들 증가 | 낮음 | d3-scale + d3-array만 import. tree-shaking 적용. |
| MetricsPanel 성능 저하 | 중간 | uPlot 백업 플랜 있음. 측정 후 결정. |
| `LibraryDependencyGraph` 미지원 | 확정 | 보류 결정. force layout 필요시 별도 검토. |

---

## 완료 기준

Phase 54 전체 완료 조건:
- [ ] `TimeSeriesChart`, `QuotaDonut`, `Spark`, `LibraryUsageChart`, `MetricsPanel` LayerChart 교체 완료
- [ ] `npm run check` 오류 0
- [ ] dark mode + light mode 시각 동등성 확인 (dev 서버 + `/browse`)
- [ ] 번들 크기 증가 50KB gzip 미만 유지
- [ ] 작업 기록 갱신 — `openspec/changes/archive/2026-05-18-54-phase/` (구 milestone.md Phase 54)
