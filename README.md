# Afterglow

**Language:** 한국어 · [English](README.en.md)

> Horizon의 완성도 + Skyline의 현대적 UX를 결합한 차세대 OpenStack 대시보드

[![CI](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/test.yml/badge.svg)](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/test.yml)
[![Docker Build](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/docker-build.yml/badge.svg)](https://github.com/openstack-afterglow/openstack-afterglow/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/github/license/openstack-afterglow/openstack-afterglow)](LICENSE)

Afterglow는 OpenStack 클라우드를 위한 오픈소스 웹 대시보드입니다. Horizon의 기능 완성도와 안정성을 유지하면서 SvelteKit 기반의 현대적 UI/UX를 제공하고, Magnum을 대체하는 **k3s 기반 Kubernetes 프로비저닝**과 AI/ML 워크로드에 특화된 **OverlayFS 라이브러리 레이어**를 내장합니다.

## 주요 기능

- **OpenStack 전체 서비스 관리** — Nova · Glance · Cinder · Neutron · Manila · Octavia를 단일 대시보드에서
- **k3s 클러스터 프로비저닝** — Magnum 없이 VM에 k3s 직접 배포 (OCCM · Cinder/Manila CSI · Keystone Auth · Barbican KMS 플러그인)
- **OverlayFS 라이브러리 레이어 (Union Mount v2)** — content-addressable 불변 레이어, Fork API, Manila 스냅샷 백업/복원
- **모니터링 통합** — Grafana JWT 임베드, Prometheus HTTP SD, Monitoring 보안 그룹 자동화
- **Defense-in-depth 보안** — IDOR 가드, HKDF 키 분리 암호화, kubeconfig audit log, production 부팅 가드

## 빠른 시작

```bash
git clone git@github.com:openstack-afterglow/openstack-afterglow.git
cd openstack-afterglow
cp config.toml.example config.toml   # OpenStack 자격증명 입력
docker compose up -d                 # http://localhost:3000
```

Kubernetes · ArgoCD · kolla-ansible 배포와 상세 설정은 아래 문서를 참고하세요.

## 문서

📖 전체 문서: **<https://openstack-afterglow.github.io/openstack-afterglow/>**

| 문서 | 내용 |
|---|---|
| [시작하기 · 배포](docs/deployment.md) | Docker Compose · Kubernetes · ArgoCD · kolla-ansible |
| [아키텍처](docs/architecture.md) | 시스템 구조, VM 생성 플로우, OverlayFS |
| [k3s 클러스터](docs/k3s.md) | k3s 프로비저닝, 노드 구성, CoreOS 전환 |
| [API 레퍼런스](docs/api-reference.md) | 전체 REST API |
| [보안 모델](docs/security.md) | 인증·인가, IDOR 가드, HKDF 암호화, audit log |

릴리스 변경사항은 [CHANGELOG](CHANGELOG.md), 전체 로드맵은 [milestone.md](milestone.md)를 참고하세요.

## 기술 스택

| 구성 | 기술 |
|---|---|
| 프론트엔드 | SvelteKit · TypeScript · Tailwind CSS v4 |
| 백엔드 | FastAPI · openstacksdk (Python) |
| 캐시 / 세션 | Redis 7 |
| 배포 | Docker Compose · Kubernetes (Kustomize) · ArgoCD · kolla-ansible |

## 개발

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload   # 백엔드 :8000
cd frontend && npm install && npm run dev                       # 프론트엔드 :3000
npm test                                                        # 전체 테스트
```

## 라이선스

MIT License — [LICENSE](LICENSE)
