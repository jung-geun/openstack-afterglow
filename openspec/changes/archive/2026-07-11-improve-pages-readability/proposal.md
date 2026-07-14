## Why

GitHub Pages 문서는 Just the Docs remote theme를 사용하지만 버전을 고정하지 않았고, 기본 dark palette와 기본 content density가 긴 Korean technical documentation과 Mermaid diagram을 읽기 어렵게 한다.

## What Changes

- Just the Docs `v0.12.0` remote theme를 고정한다.
- Afterglow 디자인 토큰에 맞는 고대비 documentation color scheme과 readable content overrides를 추가한다.
- homepage와 class diagram index를 sidebar navigation에서 명확히 찾을 수 있게 한다.
- Mermaid browser runtime을 검증한 11.16.0으로 맞춘다.

## Capabilities

### New Capabilities

- 고대비 dark documentation reading surface와 diagram-friendly code/table treatment.

### Modified Capabilities

- GitHub Pages navigation과 Just the Docs theme delivery가 pinned release를 사용한다.

## Impact

- `docs/_config.yml`, documentation style assets, homepage/index front matter, OpenSpec 기록만 변경한다.
