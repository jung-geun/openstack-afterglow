# `frontend/src/lib/components/object-storage` 클래스 다이어그램

**대상 경로:** `frontend/src/lib/components/object-storage`

## 책임
`frontend/src/lib/components/object-storage`의 책임은 <<interface>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 4개 source type과 1개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `frontend/src/lib/components/object-storage/MoveModal.svelte`
- `frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte`
- `frontend/src/lib/components/object-storage/ObjectTrashView.svelte`

## 다이어그램 1 — `frontend/src/lib/components/object-storage/MoveModal.svelte::Props` … `frontend/src/lib/components/object-storage/ObjectTrashView.svelte::TrashObject`
```mermaid
classDiagram
%% source-type: frontend/src/lib/components/object-storage/MoveModal.svelte::Props
class T_frontend_src_lib_components_object_storage_MoveModal_svelte_Props_39493332b110["Props (frontend/src/lib/components/object-storage/MoveModal.svelte)"] {
  <<interface>>
  +bulk: boolean | undefined
}
%% source-type: frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte::ArState
class T_frontend_src_lib_components_object_storage_ObjectBrowserToolbar_svelte_ArState_9213a207b4fb["ArState (frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte)"] {
  <<interface>>
  +active: boolean
  +intervalSeconds: number
  +intervalOptions: Array~number~
}
%% source-type: frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte::Props
class T_frontend_src_lib_components_object_storage_ObjectBrowserToolbar_svelte_Props_1e95abf82df4["Props (frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte)"] {
  <<interface>>
  +ar: ArState
  +onManualRefresh: Callable~; returns void~
}
%% source-type: frontend/src/lib/components/object-storage/ObjectTrashView.svelte::TrashObject
class T_frontend_src_lib_components_object_storage_ObjectTrashView_svelte_TrashObject_1b1e41f9ce52["TrashObject (frontend/src/lib/components/object-storage/ObjectTrashView.svelte)"] {
  <<interface>>
  +trash_key: string
  +original_name: string
  +deleted_at: number
  +bytes: number
  +content_type: string | undefined
}
T_frontend_src_lib_components_object_storage_ObjectBrowserToolbar_svelte_Props_1e95abf82df4 --> T_frontend_src_lib_components_object_storage_ObjectBrowserToolbar_svelte_ArState_9213a207b4fb : associates
```

### 관계 설명
- `frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte::Props --> frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte::ArState` — 근거: `frontend/src/lib/components/object-storage/ObjectBrowserToolbar.svelte::Props.ar`; 관계: `associates`.

### 타입 표기 정규화
| Mermaid 표기 | 소스 표기 |
|---|---|
| `Array~number~` | `number[]` |
| `Callable~; returns void~` | `() => void` |
