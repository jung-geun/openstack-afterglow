# `frontend/src/lib/design` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/design`

## 책임
`frontend/src/lib/design`의 책임은 <<interface>>, <<type alias>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 4개 source type과 1개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/design/tokens.ts`
- `frontend/src/lib/design/visualDebt.ts`

## 다이어그램 1 — `frontend/src/lib/design/tokens.ts::DesignTone` … `frontend/src/lib/design/visualDebt.ts::VisualDebtFinding`
```mermaid
classDiagram
%% source-type: frontend/src/lib/design/tokens.ts::DesignTone
class T_frontend_src_lib_design_tokens_ts_DesignTone_2b7705423338["DesignTone (frontend/src/lib/design/tokens.ts)"] {
  <<type alias>>
  +value: (typeof DESIGN_TONES) number
}
%% source-type: frontend/src/lib/design/visualDebt.ts::VisualDebtBaseline
class T_frontend_src_lib_design_visualDebt_ts_VisualDebtBaseline_dfc3d36105a8["VisualDebtBaseline (frontend/src/lib/design/visualDebt.ts)"] {
  <<type alias>>
  +value: Record~string; VisualDebtBaselineEntry~
}
%% source-type: frontend/src/lib/design/visualDebt.ts::VisualDebtBaselineEntry
class T_frontend_src_lib_design_visualDebt_ts_VisualDebtBaselineEntry_3976f8964782["VisualDebtBaselineEntry (frontend/src/lib/design/visualDebt.ts)"] {
  <<interface>>
  +count: number
  +tokens: readonly string
}
%% source-type: frontend/src/lib/design/visualDebt.ts::VisualDebtFinding
class T_frontend_src_lib_design_visualDebt_ts_VisualDebtFinding_86fa5659b929["VisualDebtFinding (frontend/src/lib/design/visualDebt.ts)"] {
  <<interface>>
  +token: string
  +line: number
  +column: number
}
T_frontend_src_lib_design_visualDebt_ts_VisualDebtBaseline_dfc3d36105a8 --> T_frontend_src_lib_design_visualDebt_ts_VisualDebtBaselineEntry_3976f8964782 : associates
```

### 관계 설명
- `frontend/src/lib/design/visualDebt.ts::VisualDebtBaseline --> frontend/src/lib/design/visualDebt.ts::VisualDebtBaselineEntry` — 근거: `frontend/src/lib/design/visualDebt.ts::VisualDebtBaseline.value`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `(typeof DESIGN_TONES) number` | `(typeof DESIGN_TONES)[number]` |
| `Record~string; VisualDebtBaselineEntry~` | `Record<string, VisualDebtBaselineEntry>` |
| `readonly string` | `readonly string[]` |
