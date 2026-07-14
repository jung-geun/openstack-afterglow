# `backend/app/api/object_storage` 클래스 다이어그램

**대상 경로:** `backend/app/api/object_storage`

## 책임
`backend/app/api/object_storage`의 책임은 <<class>>, <<pydantic>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 3개 source type과 0개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `backend/app/api/object_storage/containers.py`

## 다이어그램 1 — `backend/app/api/object_storage/containers.py::RestoreObjectRequest` … `backend/app/api/object_storage/containers.py::_QueueIO`
```mermaid
classDiagram
%% source-type: backend/app/api/object_storage/containers.py::RestoreObjectRequest
class T_backend_app_api_object_storage_containers_py_RestoreObjectRequest_b57deda84649["RestoreObjectRequest (backend/app/api/object_storage/containers.py)"] {
  <<pydantic>>
  +trash_key: str
}
%% source-type: backend/app/api/object_storage/containers.py::RestoreContainerRequest
class T_backend_app_api_object_storage_containers_py_RestoreContainerRequest_10500a2d5a60["RestoreContainerRequest (backend/app/api/object_storage/containers.py)"] {
  <<pydantic>>
}
%% source-type: backend/app/api/object_storage/containers.py::_QueueIO
class T_backend_app_api_object_storage_containers_py_QueueIO_3d8412c1e028["_QueueIO (backend/app/api/object_storage/containers.py)"] {
  <<class>>
  #_q: Queue~object~
  #_buf: Any
  #_done: Any
  +__init__(q: Queue~object~): void
  +read(n: int): bytes
}
```

### 관계 설명
- 없음
