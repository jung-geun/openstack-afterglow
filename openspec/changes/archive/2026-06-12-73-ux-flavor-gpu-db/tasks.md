## 72. 관리자 UX — flavor 속성 템플릿 · GPU 카탈로그 DB화 · 하이퍼바이저-GPU 통합 (2026-06-12)

### 72.1 동기

flavor extra spec은 키/값을 손으로 입력해야 해 오타·형식 실수가 잦았고, GPU alias 카탈로그는
코드 내장 + config.toml로만 로드되어 관리자가 재배포 없이 alias를 추가할 수 없었다.
관리자 페이지의 하이퍼바이저/GPU 페이지가 분리되어 호스트 리소스 현황을 한 화면에서 볼 수 없었다.

### 72.2 구현

- [x] GPU 장치 카탈로그 DB화 — `gpu_device_catalog` 테이블 + `gpu_catalog.py` 서비스 +
  `GET/POST/DELETE /api/admin/gpu-devices` + CSV 일괄 import(`replace` 기본/`upsert` 옵션) +
  `PCI_DEVICE_MAP` in-place 갱신(startup·변경 시) + pytest
- [x] flavor 속성 템플릿 — `flavorSpecTemplates.ts` 카탈로그(GPU/CPU/메모리/QoS) +
  FlavorExtraSpecsTab 템플릿 선택 UI(`pci_passthrough:alias`는 alias 드롭다운+개수) +
  GPU 장치 카탈로그 관리 모달(flavor 페이지, 단건 추가/CSV 업로드)
- [x] 하이퍼바이저-GPU 페이지 통합 — hypervisors 페이지에서 gpu-hosts 조인,
  GPU 컬럼(vCPU·RAM과 동일 사용량 바), GPU 종류 필터 칩, 상세 패널 GPU 장치 섹션,
  `/admin/gpu` 삭제+리다이렉트

