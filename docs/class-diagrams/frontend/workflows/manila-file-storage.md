---
layout: default
title: Manila file storage workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 6
---

# Manila file storage workflow

**진입점:** `frontend/src/routes/dashboard/file-storage/+page.svelte`의 `FileStorageWizard`는 share type·share network·access rule을 단계적으로 준비하고 Manila file storage를 생성한다.

## Sequence

```mermaid
sequenceDiagram
actor User
participant Page as file storage page
participant Wizard as FileStorageWizard
participant Store as FileStorageWizardStore
participant API as /api/v1 file-storage
participant Networks as share-network + network APIs
participant Rules as access-rules API

Page->>API: GET file-storage + quota
User->>Wizard: type/network/access 설정
Wizard->>Store: loadInitialData()
Store->>API: GET /file-storage/types
Store->>Networks: GET /share-networks
opt inline share network 생성
  Store->>Networks: GET network detail/subnets
  Store->>Networks: POST /share-networks
end
Wizard->>Store: createFileStorage()
Store->>API: POST /file-storage
API-->>Store: FileStorage
Store->>Rules: GET /file-storage/{id}/access-rules
opt access rule 추가
  Store->>Rules: POST /file-storage/{id}/access-rules
end
Store-->>Wizard: step 3 result
Wizard-->>Page: onCreated()
Page->>API: GET /file-storage refresh
```

## 시나리오 클래스

```mermaid
classDiagram
class FileStorageWizardModule["frontend/src/lib/components/file-storage/wizard/FileStorageWizard.svelte"] {
  <<component>>
}
class FileStorageWizardStoreModule["frontend/src/lib/stores/fileStorageWizardStore.svelte.ts"] {
  <<module>>
  +createFileStorageWizardStore()
}
class FileStorage["frontend/src/lib/types/fileStorage.ts::FileStorage"] {
  <<interface>>
}
class ShareTypeMeta["frontend/src/lib/stores/fileStorageWizardStore.svelte.ts::ShareTypeMeta"] {
  <<interface>>
}
class ShareNetwork["frontend/src/lib/stores/fileStorageWizardStore.svelte.ts::ShareNetwork"] {
  <<interface>>
}
class NeutronNetwork["frontend/src/lib/stores/fileStorageWizardStore.svelte.ts::NeutronNetwork"] {
  <<interface>>
}
class AccessRule["frontend/src/lib/stores/fileStorageWizardStore.svelte.ts::AccessRule"] {
  <<interface>>
}
class ApiClientModule["frontend/src/lib/api/client.ts"] {
  <<module>>
}

FileStorageWizardModule --> FileStorageWizardStoreModule : provides actions
FileStorageWizardStoreModule --> ShareTypeMeta : selects share type
FileStorageWizardStoreModule --> ShareNetwork : selects or creates
ShareNetwork --> NeutronNetwork : maps neutron network
FileStorageWizardStoreModule --> FileStorage : creates
FileStorage --> AccessRule : exposes access rules
FileStorageWizardStoreModule --> ApiClientModule : requests
```

## 근거

- `fileStorageWizardStore.svelte.ts`는 `/api/v1/file-storage/types`, `/api/v1/share-networks`, `/api/v1/networks/{id}`를 사용해 wizard option을 채운다.
- 생성은 `/api/v1/file-storage` POST이며 생성 뒤 access-rule 목록을 조회하고 필요 시 `/access-rules` POST를 수행한다.
