---
layout: default
title: VM 생성 workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 1
---

# VM 생성 workflow

**진입점:** `frontend/src/lib/components/VmCreatePanel.svelte`는 `createVmCreateStore()`를 만들고 wizard context에 제공한다. `VmCreateStore.deploy()`가 일반 VM 또는 squashfs consume VM을 선택해 long-running 생성 상태를 화면에 반영한다.

## Sequence

```mermaid
sequenceDiagram
actor User
participant Panel as VmCreatePanel
participant Store as VmCreateStore
participant Wizard as wizard state
participant API as /api/v1 instances async
participant Progress as SSE response body
participant UI as toast + goto

User->>Panel: wizard 입력 후 배포
Panel->>Store: deploy()
Store->>Wizard: image/flavor/network/mount 선택값 읽기
alt squashfs consume 조건 충족
  Store->>API: POST /api/v1/libraries/squashfs/consume
  API-->>Store: consume response
else 일반 또는 admin VM
  Store->>API: POST /api/v1/instances/async 또는 /api/v1/admin/instances/async
  loop data: progress event
    API-->>Progress: step, progress, message, error
    Progress-->>Store: state 갱신
  end
end
Store-->>UI: success/error toast
Store->>Wizard: resetWizard() + closeWizard()
Store->>UI: goto(/dashboard 또는 /admin/instances)
```

## 시나리오 클래스

```mermaid
classDiagram
class VmCreatePanelModule["frontend/src/lib/components/VmCreatePanel.svelte"] {
  <<component>>
}
class VmCreateStoreModule["frontend/src/lib/stores/vmCreateStore.svelte.ts"] {
  <<module>>
  +createVmCreateStore()
  +deploy()
}
class WizardModule["frontend/src/lib/stores/wizard.ts"] {
  <<module>>
}
class ProgressMessage["frontend/src/lib/stores/vmCreateStore.svelte.ts::ProgressMessage"] {
  <<interface>>
  +step: string
  +progress: number
  +message: string
}
class InstanceAsyncEndpoint["/api/v1/instances/async"] {
  <<HTTP endpoint>>
}
class SquashfsConsumeEndpoint["/api/v1/libraries/squashfs/consume"] {
  <<HTTP endpoint>>
}

VmCreatePanelModule --> VmCreateStoreModule : creates and provides
VmCreateStoreModule --> WizardModule : reads selection
VmCreateStoreModule --> InstanceAsyncEndpoint : POST and streams
VmCreateStoreModule --> SquashfsConsumeEndpoint : POST when eligible
InstanceAsyncEndpoint --> ProgressMessage : emits
```

## 근거

- `vmCreateStore.svelte.ts::deploy`는 일반 경로에서 `/api/v1/instances/async` 또는 `/api/v1/admin/instances/async`에 `fetch` POST하고 SSE-like `data:` line을 소비한다.
- 같은 함수는 squashfs 선택 시 `/api/v1/libraries/squashfs/consume`을 별도 JSON POST로 호출한다.
- 완료 시 wizard reset/close와 `goto()`를 수행한다.
