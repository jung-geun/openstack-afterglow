---
layout: default
title: Frontend 리소스 workflow
parent: 클래스 다이어그램
has_children: true
nav_order: 3
---

# Frontend 리소스 Workflow 다이어그램

이 문서는 사용자 작업이 SvelteKit route, component, Svelte 5 store/controller, API transport, FastAPI `/api/v1` endpoint를 통과하는 순서를 설명한다. 클래스 다이어그램은 실제 named type과 canonical source-path를 가진 `<<route>>`, `<<component>>`, `<<module>>` 노드를 함께 사용한다.

## Workflow

- [VM 생성](./vm-instance.md)
- [Drover K3s 생성](./drover-k3s.md)
- [Load balancer 생성](./load-balancer.md)
- [Network와 router 생성](./network-router.md)
- [Block volume 생성](./block-volume.md)
- [Manila file storage 생성](./manila-file-storage.md)
- [Object storage 버킷과 object 관리](./object-storage.md)

## 공통 규칙

- resource 호출은 `api` client, direct streaming `fetch`, 또는 SSE helper를 통해 인증 token과 project context를 전달한다.
- mutation 성공 뒤에는 route-local fetch, controller fetch 또는 navigation으로 화면 상태를 갱신한다.
- long-running VM·K3s 작업은 HTTP body/SSE progress를 소비하고, 나머지 resource 생성은 완료 응답 뒤 목록을 다시 읽는다.
