## 1. Manila NFS Share 지원 추가

> **목표**: 기존 CephFS 전용 Manila 연결을 NFS 프로토콜로 확장하여, VM에서 NFS 마운트로 파일 스토리지 접근 가능하게 구현

- [x] 1.1 Manila NFS share 생성 기능 구현
  - [x] `share_proto="NFS"` 옵션으로 Manila share 생성 API 연동
  - [x] NFS 전용 share type 지원 (`nfstype` 등 환경별 설정)
  - [x] `backend/app/services/manila.py` — NFS share 생성/삭제/조회 함수 추가
  - [x] `backend/app/models/storage.py` — NFS 관련 필드 추가 (`share_proto`, `nfs_export_location`)
  - [x] `config.toml.example` — NFS용 설정 항목 추가 (`os_manila_nfs_share_type`)

- [x] 1.2 NFS access rule 관리
  - [x] NFS access rule 생성: `access_type="ip"`, `access_to="<VM_IP_OR_CIDR>"`
  - [x] VM Floating IP / Tenant 네트워크 CIDR 기반 자동 access rule 등록
  - [x] VM 생성 시 인스턴스 IP 확보 후 NFS share access rule 자동 추가
  - [x] VM 삭제 시 관련 NFS access rule 자동 정리 — `delete_instance()`에서 VM IP 매칭 후 revoke (best-effort)

- [x] 1.3 NFS 마운트 안정성 확보
  - [x] NFS 마운트 옵션 튜닝: `hard,intr,noatime,_netdev` 기본값
  - [x] 재연결 정책: `timeo=10,retrans=3` 으로 일시적 네트워크 장애 대응
  - [x] systemd 마운트 유닛(`union-overlay.service`) — `After=network-online.target remote-fs.target`
  - [ ] NFS 마운트 상태 헬스체크 스크립트 추가 (5.1로 이동)

- [x] 1.4 Frontend — NFS 옵션 UI
  - [x] 파일 스토리지 생성 시 프로토콜 선택 (CEPHFS / NFS) 드롭다운 추가
  - [x] NFS share 목록 및 access rule 관리 UI
  - [x] VM 생성 마법사에서 마운트 프로토콜 선택 옵션 — `SelectStrategy.svelte` Strategy B에 NFS/CephFS 토글, `wizard.ts` mountProtocol 상태 추가, 라이브러리별 프로토콜 배지

---

