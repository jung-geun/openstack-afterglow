# login-logo-branding

## Goal
로그인 페이지에서 배경별 로고를 설정하고 관리자 UI에서 업로드/초기화할 수 있게 한다.

## Scope
- `[app]` 설정과 public site config에 `logo_dark_path`, `logo_light_path`를 추가한다.
- 로그인 헤더가 resolved theme에 맞춰 light/dark 로고 variant를 선택하고 legacy `logo_path`로 fallback한다.
- DB-backed `site_branding_assets` 테이블과 `/api/v1/site-config` 하위 public/admin branding endpoints를 추가한다.
- 관리자 개요 페이지에 로그인 로고 업로드/초기화 패널을 추가한다.
- 업로드는 1 MiB 이하 PNG/JPEG/WebP/GIF magic bytes만 허용하고 detected content type으로 저장한다.

## Non-goals
- Sidebar/AdminSidebar/navigation 로고 변경.
- SVG/XML/HTML 로고 업로드 지원.
- DB unavailable 상태에서 admin upload/reset fallback 저장소 제공.
