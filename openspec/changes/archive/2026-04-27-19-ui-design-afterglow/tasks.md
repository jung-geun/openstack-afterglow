## 15. UI/Design — Afterglow 브랜드 리디자인

### 15.1 진행 현황

- [x] Phase 1: `@theme` 토큰 블록, Geist 폰트, `RingMark.svelte` 컴포넌트화
- [x] Phase 2: `statusColors.ts` → 5 semantic tone 재작성, `StatusChip.svelte` dot pulse
- [x] Phase 3: 사이드바 active warm soft + 좌측 strip, `StatTile`/`QuotaBar` accent 토큰화
- [x] Phase 3.5: 라이트 모드 warm WCAG AA 보정 (orange-600/700 오버라이드)
- [x] Phase 6a: `--gradient-brand/warm`, `--glow-warm/accent` 토큰, `GradientText.svelte`, VM 생성 버튼 warm gradient
- [x] Phase 6b: `StatTile` 아이콘 칩 radial halo + glow
- [x] Phase 6c: 위저드 스테퍼 warm gradient (완료/현재 step 원 + connector)
- [x] Phase 6d: `Toast` actionable 링크 (`action?: { label, onClick }`) + 토큰 기반 색상
- [x] Phase 6e: `EmptyState.svelte` warm halo 신규 컴포넌트
- [x] Phase 6f: `Card.svelte` 좌상단 radial warm highlight
- [x] Phase 7: `Button.svelte` variant 컴포넌트 (primary/secondary/ghost/danger × sm/md/lg), primary CTA 15곳 warm gradient 통일
- [x] Phase 5a: `DetailHeader.svelte` 상세 페이지 헤더 통일 (Instance/K3s/LB/Router/Volume/FileStorage 6종)
- [x] Phase 5d: Cmd-K 팔레트 (`nav.ts` 추출, `palette.ts` store, `CmdPalette.svelte`, 상단바 ⌘K 트리거)
- [x] Phase 5e: 대시보드 `TopologyCard.svelte` wrapper 임베드 (GlobalTopology 무변경)
- [ ] Phase 4: `layout.css` override sheet 제거 (336 → ~70 라인)

### 15.2 검증 (사용자 직접)

- [ ] 다크모드: 대시보드 username warm gradient 텍스트, 사이드바 VM 생성 버튼 warm gradient glow
- [ ] 라이트모드: 사이드바 active 항목이 진한 오렌지 텍스트 + 좌측 strip 명확히 보임
- [ ] 다크/라이트 토글 시 사이드바 active 자연스럽게 전환
- [ ] 인스턴스/볼륨 페이지 StatusChip BUILD/CREATING 상태 dot pulse 동작
- [ ] VM 생성 위저드 스테퍼 완료/현재 step warm gradient 적용 확인
- [ ] ⌘K 팔레트: 라우트 jump + 리소스 검색 fuzzy match + 상단바 버튼 트리거 동작 확인
- [ ] 인스턴스/K3s/LB/Router/Volume/FileStorage 상세 헤더 `DetailHeader` 통일 확인
- [ ] 대시보드 하단 네트워크 토폴로지 카드 노출 + 전체보기 링크 동작

