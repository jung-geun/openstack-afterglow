## Why

테넌트 네트워크 내부 인스턴스에 접근하는 안전한 단일 진입점(bastion)이 없다. 현재는 인스턴스별 Floating IP 또는 router를 통한 인터넷 노출에 의존해야 하며, 이는 공격 표면을 넓힌다. [wg-easy](https://github.com/wg-easy/wg-easy)를 모티브로 한 **Waygate**(WireGuard 기반 보안 게이트웨이)를 OpenStack 대시보드(Afterglow)에 통합해, 클라이언트 발급·관리·연결 모니터링을 대시보드에서 수행하고 테넌트 네트워크 접근을 Waygate 단일 경로로 좁힌다.

## What Changes

- provider 네트워크에 WireGuard VPN 인스턴스를 프로비저닝한다(flavor `cpu.1c_2g`). 인스턴스 내부 에이전트가 Afterglow 백엔드와 pull/reconcile 방식으로 연동되어 peer 상태를 동기화하고 연결 상태를 보고한다(inbound 관리 포트 없음).
- Afterglow가 클라이언트 키쌍(X25519)을 생성·AES-256-GCM 암호화 저장하여 `.conf`/QR 재발급을 지원한다. 서버 키쌍은 VM 내부에서 생성되고 public key만 보고되며, private key는 백엔드에 저장되지 않는다.
- VPN 인스턴스에 여러 테넌트 네트워크를 추가로 연결할 수 있다(멀티 NIC + SNAT masquerade).
- VPN 서버 설정(클라이언트 인증정보·라우팅 정보)을 백업(export)하고 다른 WireGuard 서버로 마이그레이션(import)할 수 있다. 실제 서버 키는 마이그레이션 대상에서 새로 생성되므로 제외된다.

## Capabilities

### New Capabilities

- **vpn-server-provisioning**: provider 네트워크 기반 WireGuard VPN 인스턴스 생성/조회/삭제, 테넌트 프로젝트 스코프 부팅.
- **vpn-client-management**: VPN 클라이언트(peer) 발급/조회/활성화 토글/삭제, `.conf` 다운로드, QR 코드 발급.
- **vpn-agent-reconcile**: VM 내부 에이전트 ↔ 백엔드 간 베어러 토큰 인증 register/desired-state/status 엔드포인트(pull 모델).
- **vpn-network-attachment**: VPN 서버에 테넌트 네트워크 추가 연결/해제.
- **vpn-backup-migration**: VPN 서버 설정 export/import(서버 키 제외, 클라이언트 정보·라우팅 정보 이전).

### Modified Capabilities

- 없음 (신규 기능, 기존 엔드포인트/모델 변경 없음).

## Technical Namespace Cutover

- [ ] `vpn` API/config/module/table/Redis/agent/frontend namespace를 `waygate`로 clean cutover 한다. 이전 VPN 인스턴스는 없으므로 데이터 이전·호환 경로·리다이렉트는 제공하지 않는다.

## Impact

- **백엔드**: `app/models/db.py`에 `VpnServer`/`VpnClient`/`VpnNetworkAttachment` 테이블 추가. `app/api/vpn/` 신규 라우터(`/api/v1/vpn`), `app/main.py`의 `_AUDIT_PREFIX_MAP`에 항목 추가. `app/services/`에 provisioner/config/crypto/keys/ipam 신규 서비스. `app/templates/`에 VPN cloud-init 템플릿 추가. `afterglow.conf.example`/`app/config.py`/`generate_k8s.py`에 `[vpn]` 섹션 동기화.
- **프론트엔드**: `frontend/src/routes/dashboard/network/vpn/` 신규 라우트, `frontend/src/lib/api/vpn.ts` 신규 API 클라이언트, `Sidebar.svelte`에 VPN 메뉴 추가.
- **테스트**: `backend/tests/`에 프로비저닝/클라이언트/에이전트/보안(인젝션 회귀)/암호화 pytest 신규 추가.
- **기존 기능에 대한 영향 없음** — 신규 격리된 리소스 타입이며 기존 네트워크/인스턴스 API를 변경하지 않는다.
