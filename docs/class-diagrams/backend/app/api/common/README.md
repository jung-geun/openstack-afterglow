# `backend/app/api/common` 클래스 다이어그램

**대상 경로:** `backend/app/api/common`

## 책임
`backend/app/api/common`의 책임은 <<pydantic>>으로 표현되는 운영 타입 계약을 정의하는 것이다.
이 문서는 7개 source type과 3개 정적 관계를 1개 Mermaid class diagram으로 나누어 보여준다.

## 포함 파일
- `backend/app/api/common/libraries.py`
- `backend/app/api/common/site.py`

## 다이어그램 1 — `backend/app/api/common/libraries.py::ValidateLibrariesRequest` … `backend/app/api/common/site.py::BrandingStatusResponse`
```mermaid
classDiagram
%% source-type: backend/app/api/common/libraries.py::ValidateLibrariesRequest
class T_backend_app_api_common_libraries_py_ValidateLibrariesRequest_ace090398a18["ValidateLibrariesRequest (backend/app/api/common/libraries.py)"] {
  <<pydantic>>
  +library_ids: list~str~
  +ubuntu_version: str | None
}
%% source-type: backend/app/api/common/libraries.py::ValidateLibrariesResponse
class T_backend_app_api_common_libraries_py_ValidateLibrariesResponse_62dfef2ab175["ValidateLibrariesResponse (backend/app/api/common/libraries.py)"] {
  <<pydantic>>
  +compatible: bool
  +messages: list~str~
}
%% source-type: backend/app/api/common/site.py::SiteServicesResponse
class T_backend_app_api_common_site_py_SiteServicesResponse_48c768a34526["SiteServicesResponse (backend/app/api/common/site.py)"] {
  <<pydantic>>
  +magnum: bool
  +manila: bool
  +zun: bool
  +k3s: bool
  +trove: bool
  +swift: bool
  +barbican: bool
}
%% source-type: backend/app/api/common/site.py::PublicSiteConfigResponse
class T_backend_app_api_common_site_py_PublicSiteConfigResponse_e6044d00e7c3["PublicSiteConfigResponse (backend/app/api/common/site.py)"] {
  <<pydantic>>
  +site_name: str
  +site_description: str
  +logo_path: str
  +logo_dark_path: str
  +logo_light_path: str
  +favicon_path: str
  +services: SiteServicesResponse
}
%% source-type: backend/app/api/common/site.py::BrandingSlotResponse
class T_backend_app_api_common_site_py_BrandingSlotResponse_e826496bb3f5["BrandingSlotResponse (backend/app/api/common/site.py)"] {
  <<pydantic>>
  +field: str
  +label: str
  +description: str
}
%% source-type: backend/app/api/common/site.py::BrandingAssetResponse
class T_backend_app_api_common_site_py_BrandingAssetResponse_97d745b54402["BrandingAssetResponse (backend/app/api/common/site.py)"] {
  <<pydantic>>
  +slot: str
  +filename: str
  +content_type: str
  +size_bytes: int
  +sha256: str
  +url: str
  +updated_at: str
  +updated_by_user_id: str | None
}
%% source-type: backend/app/api/common/site.py::BrandingStatusResponse
class T_backend_app_api_common_site_py_BrandingStatusResponse_e046fb97ebdc["BrandingStatusResponse (backend/app/api/common/site.py)"] {
  <<pydantic>>
  +slots: dict~str; BrandingSlotResponse~
  +effective: dict~str; str~
  +assets: dict~str; BrandingAssetResponse | None~
}
T_backend_app_api_common_site_py_PublicSiteConfigResponse_e6044d00e7c3 --> T_backend_app_api_common_site_py_SiteServicesResponse_48c768a34526 : associates
T_backend_app_api_common_site_py_BrandingStatusResponse_e046fb97ebdc --> T_backend_app_api_common_site_py_BrandingSlotResponse_e826496bb3f5 : associates
T_backend_app_api_common_site_py_BrandingStatusResponse_e046fb97ebdc --> T_backend_app_api_common_site_py_BrandingAssetResponse_97d745b54402 : associates
```

### 관계 설명
- `backend/app/api/common/site.py::PublicSiteConfigResponse --> backend/app/api/common/site.py::SiteServicesResponse` — 근거: `backend/app/api/common/site.py::PublicSiteConfigResponse.services`; 관계: `associates`.
- `backend/app/api/common/site.py::BrandingStatusResponse --> backend/app/api/common/site.py::BrandingSlotResponse` — 근거: `backend/app/api/common/site.py::BrandingStatusResponse.slots`; 관계: `associates`.
- `backend/app/api/common/site.py::BrandingStatusResponse --> backend/app/api/common/site.py::BrandingAssetResponse` — 근거: `backend/app/api/common/site.py::BrandingStatusResponse.assets`; 관계: `associates`.
