# admin-basic-settings-branding

## Goal
관리자 개요에 섞여 있던 로그인 로고 설정을 별도 기본 설정 페이지로 분리하고 Drover 클러스터 카드 아이콘을 Kubernetes 아이콘으로 교체한다.

## Scope
- `/admin` 관리자 개요에서 로그인 로고 브랜딩 패널을 제거한다.
- 새 `/admin/settings` 기본 설정 페이지를 만들고 로그인 로고 브랜딩 패널을 그 안에 배치한다.
- 관리자 사이드바와 nav config에 기본 설정 진입점을 추가한다.
- 사용자 대시보드 Drover 클러스터 stat tile 아이콘을 Kubernetes wheel mark로 교체한다.
- focused frontend 테스트/체크로 라우팅 및 컴포넌트 계약을 검증한다.
