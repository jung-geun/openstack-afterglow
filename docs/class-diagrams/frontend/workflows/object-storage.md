---
layout: default
title: Object storage workflow
parent: Frontend 리소스 workflow
grand_parent: 클래스 다이어그램
nav_order: 7
---
# Object storage workflow

버킷 목록 page는 container·trash·account metadata를 병렬 조회한다. 개별 버킷의 object 작업은 `ObjectBrowserStore`가 list, metadata, delete, rename, move, download-token을 수행한다.

## Bucket sequence

```mermaid
sequenceDiagram
actor User
participant Page as bucket page
participant Dialog as BucketCreateDialog
participant API as /api/v1/object-storage
participant Cards as BucketCardGrid

Page->>API: GET containers, trash containers, account
API-->>Page: SwiftContainer[] + AccountMeta
User->>Dialog: bucket name 제출
Dialog->>Page: createContainer(name)
Page->>API: POST /api/v1/object-storage
API-->>Page: success
Page->>API: GET containers/trash/account refresh
Page-->>Cards: refreshed SwiftContainer[]
```

## Object browser sequence

```mermaid
sequenceDiagram
actor User
participant Browser as ObjectBrowserStore
participant API as object-storage objects API
participant Queue as uploadQueue

Browser->>API: GET container metadata and objects
User->>Browser: delete/rename/move/directory action
Browser->>API: DELETE or POST object endpoint
API-->>Browser: success
Browser->>Browser: doRefresh()
opt user download
  Browser->>API: POST download-token
  API-->>Browser: temporary URL
end
opt upload
  Browser->>Queue: enqueue upload state
  Queue-->>Browser: completion refresh
end
```

## 시나리오 클래스

```mermaid
classDiagram
class BucketRouteModule["frontend/src/routes/dashboard/object-storage/buckets/+page.svelte"] {
  <<route>>
  +load()
  +createContainer()
}
class ObjectBrowserStoreModule["frontend/src/lib/stores/objectBrowser.svelte.ts"] {
  <<module>>
  +createObjectBrowserStore()
  +doRefresh()
}
class ApiClientModule["frontend/src/lib/api/client.ts"] {
  <<module>>
}
class SwiftContainer["frontend/src/lib/types/objectStorage.ts::SwiftContainer"] {
  <<interface>>
}
class TreeRow["frontend/src/lib/stores/objectBrowser.svelte.ts::TreeRow"] {
  <<type alias>>
}
class ObjectBrowserOpts["frontend/src/lib/stores/objectBrowser.svelte.ts::ObjectBrowserOpts"] {
  <<interface>>
}
class AccountMeta["frontend/src/lib/types/objectStorage.ts::AccountMeta"] {
  <<interface>>
}
class UploadQueueModule["frontend/src/lib/stores/uploadQueue.ts"] {
  <<module>>
}

BucketRouteModule --> ApiClientModule : creates and lists buckets
BucketRouteModule --> SwiftContainer : renders
ObjectBrowserStoreModule --> ApiClientModule : manages objects
ObjectBrowserStoreModule --> TreeRow : produces hierarchy rows
ObjectBrowserStoreModule --> ObjectBrowserOpts : receives context
ObjectBrowserStoreModule --> UploadQueueModule : tracks uploads
BucketRouteModule --> AccountMeta : renders account quota
```

## 근거

- bucket route `load`은 container, trash container, account를 `Promise.allSettled`로 조회한다.
- `createContainer`은 `/api/v1/object-storage` POST 후 `load()`를 다시 호출한다.
- `objectBrowser.svelte.ts`는 object list, bulk-delete, metadata, directory, rename, move, download-token endpoints를 route-local controller로 감싼다.
