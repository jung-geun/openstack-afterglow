## 33. VM 생성 위저드 디자인 시스템 반영 (2026-05-13)

### 33.1 동기

- Afterglow Design System 번들 (`vm-wizard-improved.html`) 에서 도출된 6단계 위저드 시각/구조 개선.
- 현 위저드는 step indicator 평탄, quota 변화가 음수 표기로 직관성 낮음, cloud-init 일반 textarea, review 단조로움.
- 색상 변경 없이 **구조/타이포/radius/레이아웃만** 반영 (primary = blue-500/600 유지).

### 33.2 신규 컴포넌트

- [x] `frontend/src/lib/components/wizard/WizardStepper.svelte` — progress fill bar (warm gradient) + done dot 클릭 이동
- [x] `frontend/src/lib/components/wizard/WizardHeader.svelte` — 큰 타이틀 + STEP n/6 subtitle + 새로 시작 / ✕
- [x] `frontend/src/lib/components/wizard/WizardFooter.svelte` — selection chips strip (이미지·플레이버·라이브러리) + 네비게이션

### 33.3 기존 컴포넌트 개선

- [x] `SelectImage.svelte` — 검색바 + OS chip count + hover lift + check pill
- [x] `SelectFlavor.svelte` — quota delta 미터 grid (현재 회색 + 이번 VM 추가 blue fill), GPU stock pill delta
- [x] `SelectLibraries.svelte` — 의존성 met (✓ green) / missing (! red) 칩 + 버전/req 배지 + 하단 summary strip
- [x] `SelectStrategy.svelte` — list-card 패턴 + 우측 size-slot (⚡ ~30초 / ⏱ ~3-5분)
- [x] `VmCreatePanel.svelte` (Settings) — 2열 grid + cloud-init 다크 코드 에디터 (bg-[#0f172a]) + toolbar placeholder + 라벨 톤 통일
- [x] `VmCreatePanel.svelte` (Review) — row grid + 플레이버 4분할 spec card (vCPU/RAM/Disk/GPU) + 각 row ✎ 수정 + deploy banner

### 33.4 검증

- [x] `npm run check` — 위저드 관련 파일 신규 에러 없음 (기존 pre-existing 에러는 다른 파일)
- [x] `npm run build` — production 빌드 통과 (4.40s)
- [ ] 브라우저 수동 검증 (인스턴스 페이지 + admin/인스턴스 페이지)
- [ ] light mode 전환 가독성 확인

### 33.6 VM 스케줄링/HA 분리 (완료)

- [x] `backend/app/models/compute.py` — `CreateInstanceRequest.scheduling` (Literal["standard","ha"], 기본 "standard") + `InstanceInfo.scheduling` 추가
- [x] `backend/app/services/nova.py` — `_server_to_info()` 에서 metadata scheduling 읽어 InstanceInfo 채움
- [x] `backend/app/api/compute/instances.py` (sync/async 두 분기) — meta 에 `scheduling`, HA 시 `HA_Enabled=True` 추가
- [x] `backend/app/api/identity/admin_instances.py` — 동일 meta 패턴 적용
- [x] `backend/tests/test_instance_scheduling.py` — 신규 8개 테스트 (model default, _server_to_info metadata 파싱)
- [x] `frontend/src/lib/stores/wizard.ts` — `scheduling: 'standard' | 'ha'` 필드 추가 (기본 'standard')
- [x] `frontend/src/lib/components/wizard/SelectStrategy.svelte` — 재작성: 섹션 A(스케줄링 항상) + 섹션 B(레이어 마운트 방식, 라이브러리 있을 때만)
- [x] `frontend/src/lib/components/VmCreatePanel.svelte` — step skip 로직 제거, selectScheduling 핸들러, canNext step4 조건, deploy body에 scheduling, footer summary 업데이트
- [x] 62개 테스트 통과, `npm run check` 신규 에러 없음

### 33.5 향후 (별 PR)

- cloud-init YAML 실시간 검증 (js-yaml 도입) + 예제 프리셋 적용
- review deploy banner cost 추정 ($/hour → backend cost API 필요)
- OS 별 logo 컬러 매핑 (메모리 규칙 재확인 후)
- HA evacuate 실제 동작: cluster 에 Masakari 설치 + segment/host 등록 필요 (운영 문서 별도)

