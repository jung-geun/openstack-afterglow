# `backend/app/api` 클래스 다이어그램

**대상 경로:** `backend/app/api`

## 책임
`backend/app/api`의 책임은 <<dataclass>>, <<pydantic>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 2개 source type과 0개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `backend/app/api/container/containers.py`
- `backend/app/api/deps.py`

## 다이어그램 1 — `backend/app/api/container/containers.py::ExecRequest` … `backend/app/api/deps.py::CacheMode`
```mermaid
classDiagram
%% source-type: backend/app/api/container/containers.py::ExecRequest
class T_backend_app_api_container_containers_py_ExecRequest_8d61fb7d2302["ExecRequest (backend/app/api/container/containers.py)"] {
  <<pydantic>>
  +command: str
}
%% source-type: backend/app/api/deps.py::CacheMode
class T_backend_app_api_deps_py_CacheMode_044b8f125c3b["CacheMode (backend/app/api/deps.py)"] {
  <<dataclass>>
  +enabled: bool
  +refresh: bool
}
```

### 관계 설명
- 없음
