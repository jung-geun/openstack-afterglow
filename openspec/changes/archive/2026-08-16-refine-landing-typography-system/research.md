## Rendered baseline

- Desktop hero title rendered in MaruBuri at 84px/600 inside a 466px column and occupied five lines (`466 × 428px`). The result read as a literary or institutional brochure rather than a cloud operations product.
- The same serif family carried body copy and dense interface text, which weakened the visual relationship between the introduction and the operations board.
- `Geist` and `Geist Mono` appeared in CSS fallbacks but were not bundled as an explicit, reliable Korean typography dependency.
- Mobile, tablet, desktop, light, and dark captures confirmed that the mismatch was systemic rather than theme-specific.

## Official-source comparison

| Candidate | Intended role | License / web format | Local payload sampled | Decision |
| --- | --- | --- | ---: | --- |
| [Pretendard](https://github.com/orioncactus/pretendard) | Korean body and UI | SIL OFL 1.1; variable WOFF2, 45–920 | 2,009KB | Select. Broad Korean coverage and neutral UI rhythm. |
| [IBM Plex Sans KR](https://github.com/IBM/plex/tree/master/packages/plex-sans-kr) | Technical display | SIL OFL 1.1; static WOFF2 | 432KB medium, 427KB semibold | Select. Open forms and a stronger technical voice than the current serif. |
| [IBM Plex Mono](https://github.com/IBM/plex/tree/master/packages/plex-mono) | Operational metadata | SIL OFL 1.1; static WOFF2 | 48KB regular, 49KB medium | Select. Compact resource/status rhythm with Pretendard fallback for Korean. |
| [Wanted Sans](https://github.com/wanteddev/wanted-sans) | Korean body or display | SIL OFL 1.1; variable WOFF2 | 1,259KB | Do not select. Modern and capable, but too close to the body role to create useful hierarchy. |
| [Paperlogy](https://github.com/Freesentation/paperlogy) | Expressive display | SIL OFL 1.1; static WOFF2 | 430KB semibold | Do not select. Rounded, promotional character competes with the operational product voice. |
| [SUIT](https://github.com/sunn-us/SUIT) | Korean UI | SIL OFL 1.1; static/variable webfont distributions | Not bundled | Do not select. A sound UI option, but Pretendard already covers the role with fewer active families. |

## Selected system

Use three locally hosted families: Pretendard Variable for body/UI, IBM Plex Sans KR medium and semibold for public display headings, and IBM Plex Mono regular and medium for operational metadata. This replaces roughly 15MB of five TTF MaruBuri files with roughly 3MB of WOFF2 assets, removes undeclared runtime font assumptions, and keeps display styling out of the application console.

The existing operations board and bounded product plates already explain the service model. Typography is the actual gap, so no generated illustration is planned unless the post-change captures reveal a specific missing concept.
