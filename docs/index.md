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
| [k3s 클러스터](k3s.md) | k3s 프로비저닝 및 노드 관리 |
| [아키텍처](architecture.md) | 시스템 설계 및 플로우 |
| [API 레퍼런스](api-reference.md) | REST API 전체 명세 |

---

## 핵심 특징

### k3s 클러스터 프로비저닝
OpenStack VM에 k3s를 직접 설치하여 Kubernetes 환경을 즉시 제공합니다. Magnum의 복잡한 설정 없이, cloud-init 기반으로 마스터/워커 노드를 자동 구성합니다.

### OverlayFS 라이브러리 레이어
Manila NFS/CephFS share를 OverlayFS lower layer로 마운트, AI/ML 라이브러리(Python, PyTorch, vLLM)를 여러 VM이 공유합니다. 스토리지 효율과 부팅 속도를 동시에 달성합니다.

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

[GitHub 저장소](https://github.com/jung-geun/openstack-afterglow){: .btn .btn-primary }
