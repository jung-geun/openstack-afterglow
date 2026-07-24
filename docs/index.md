---
layout: home
title: Afterglow
lang: ko
nav_order: 1
---

# Afterglow

**Language:** 한국어 · [English](en/)

> 차세대 OpenStack 대시보드 — Horizon의 완성도 + Skyline의 현대적 UX

Afterglow는 OpenStack 클라우드 환경을 위한 오픈소스 웹 대시보드입니다. 기존 Horizon의 안정성과 기능 완성도를 유지하면서, Skyline의 현대적인 UI/UX를 결합합니다. 또한 Magnum을 대체하는 **k3s 기반 Kubernetes 프로비저닝**을 내장합니다.

---

## 빠른 링크

| 문서 | 설명 |
|---|---|
| [시작하기](deployment.md) | Docker Compose / Kubernetes 배포 |
| [kolla-ansible 배포](deployment.md#kolla-ansible-배포) | OpenStack 환경 내 단일 플레이북 배포 |
| [k3s 클러스터](k3s.md) | k3s 프로비저닝 및 노드 관리 |
| [유니온 레이어 API](api/union.md) | Content-addressable OverlayFS 공유 라이브러리 레이어 (seal/fork/build) |
| [Drover 동작 명세](drover-workflow.md) | Drover 클러스터 생성의 계획 대비 현재 동작과 실제 프로비저닝 워크플로우 |
| [아키텍처](architecture.md) | 시스템 설계 및 플로우 |
| [API 레퍼런스](api-reference.md) | REST API 전체 명세 |
| [국소 기능테스트](testing.md) | 개발 중 빠르게 실행할 테스트 타깃 선택 가이드 |
| [클래스·workflow 다이어그램](class-diagrams/) | 모듈 관계와 주요 resource 작업 흐름 |

---

## 핵심 특징

### k3s 클러스터 프로비저닝
OpenStack VM에 k3s를 직접 설치하여 Kubernetes 환경을 즉시 제공합니다. Magnum의 복잡한 설정 없이, cloud-init 기반으로 마스터/워커 노드를 자동 구성합니다.

### OverlayFS 라이브러리 레이어
Manila NFS/CephFS share를 OverlayFS lower layer로 마운트, AI/ML 라이브러리(Python, PyTorch, vLLM)를 여러 VM이 공유합니다. 스토리지 효율과 부팅 속도를 동시에 달성합니다.

### 모니터링 통합
Grafana JWT 임베드를 통해 대시보드를 직접 삽입하고, Prometheus http_sd로 VM 고정 IP 기반 노드 익스포터 타깃을 자동 노출합니다. 신규 프로젝트·인스턴스 생성 시 Monitoring ingress SG를 자동으로 연결합니다.

### kolla-ansible 통합
`deploy/kolla/` 역할 및 `install.sh`를 이용해 단일 플레이북으로 OpenStack 환경 내에 Afterglow를 배포합니다.

### 완전한 OpenStack 서비스 커버리지
Nova, Glance, Cinder, Neutron, Manila, Octavia — 모든 핵심 서비스를 단일 대시보드에서 관리합니다.

---

## 기술 스택

| 구성 요소 | 기술 |
|---|---|
| 프론트엔드 | SvelteKit + TypeScript + Tailwind CSS v4 |
| 백엔드 | FastAPI + openstacksdk (Python) |
| 캐시 | Redis 7 |
| 배포 | Docker Compose / Kubernetes (Kustomize) / ArgoCD |
| CI/CD | GitHub Actions (멀티 플랫폼 Docker 빌드) |

---

[GitHub 저장소](https://github.com/openstack-afterglow/openstack-afterglow){: .btn .btn-primary }

---

## 릴리즈 노트

### v1.13.9 (2026-05-01)

#### 신규 기능
- **kolla-ansible 통합**: `deploy/kolla/` 역할 및 `install.sh` 추가 — OpenStack 환경 내에서 단일 플레이북으로 Afterglow 배포
- **Union Mount 레이어 v2**
  - Fork API — sealed(봉인된) 레이어에서 새 RW 레이어 파생
  - 동일 슬롯 중복 봉인 방지 (overwrite 금지)
  - Manila Snapshot ↔ Union 레이어 백업/복원 API
  - 빌드 완료 후 probe VM 마운트 검증
  - 백그라운드 빌드 워커 큐 (A3)
  - volume transfer 전 VM 자동 detach + rollback (A4)
  - NFS export root_squash / sec_flavor 보안 강제 (A5)
- **모니터링 통합**
  - Grafana 임베드 지원 엔드포인트 (`GET /api/v1/grafana/dashboards` — 대시보드 UID·기본 URL 반환)
  - Prometheus http_sd 타깃 엔드포인트 (`GET /api/v1/sd/prometheus/targets`) — VM 고정 IP 기반 노드 익스포터 자동 노출
  - 신규 프로젝트/인스턴스 생성 시 Monitoring ingress SG 자동 연결
- **Octavia Ingress**: per-project 관리 사용자 + App Credential 인증 모델, k8s 클러스터별 격리
- **계정 설정 페이지** (`/dashboard/account`) 신설 — 프로필, 비밀번호, 테마, 프로젝트, 키페어 통합 관리
- **Floating IP**: 연결된 인스턴스 이름 및 포트 정보 표시
- **인스턴스 볼륨** `delete_on_termination` 프론트엔드 토글
- **볼륨 스냅샷**: 프로젝트별 필터링 (admin은 전체 보기 유지)

#### 개선
- Sidebar 전면 재구성 — Identity & Access 섹션, 토폴로지 승격, 라이브러리 명칭 정리
- 여러 페이지 API 호출을 `Promise.allSettled`로 변경하여 개별 오류 격리
- 대시보드 데이터 순서대로 즉시 렌더링 (개별 API 응답 즉시 반영)
- ArgoCD auto-sync — 이미지 빌드 후 kustomization digest 자동 갱신 → ArgoCD가 새 이미지 감지 후 자동 배포

#### 버그 수정
- admin libraries 페이지 ~0.5s 무한 재갱신 루프 차단 (`untrack`)
- admin volumes 행별 액션 버튼 `...` 드롭다운으로 축약
- 볼륨 분리 오류 시 Nova 에러 메시지 클라이언트에 정확히 전달
- DB 연결 타임아웃 강제 + 대시보드 오류 격리

---

### v1.13.8 및 이전

[GitHub Releases](https://github.com/openstack-afterglow/openstack-afterglow/releases)에서 확인하세요.
