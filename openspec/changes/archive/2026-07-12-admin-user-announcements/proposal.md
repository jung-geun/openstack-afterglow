# admin-user-announcements

## Goal
관리자가 전체/특정 유저/프로젝트 대상으로 공지를 발송하고, 사용자는 통합 알림함(대시보드 카드 + 종 아이콘 + 메시지함)에서 기존 쿼터 임계 경고와 함께 확인·읽음 처리할 수 있게 한다.

## Background
대시보드 "시스템 알림" 카드는 죽은 요소가 아니라 `backend/app/api/common/dashboard.py`의 `_overview_quota_alerts()`에서 파생되는 쿼터 임계 경고에 연결되어 있었다(쿼터가 60% 안팎이라 "알림 없음"으로 보였을 뿐). 다만 헤더의 종 아이콘(`frontend/src/routes/+layout.svelte`)은 클릭 핸들러가 없는 진짜 no-op이며, 관리자가 전체 유저에게 공지를 내려보내는 채널은 존재하지 않는다. 기존 관리자 전용 `GET /api/v1/admin/notifications`는 시스템 헬스 요약(오류 인스턴스·저RAM 호스트)이지 사용자 대상 공지가 아니다.

## Scope
- `announcements` / `announcement_reads` 테이블을 신규 마이그레이션(`backend/migrations/024_announcements.sql`)과 ORM 모델(`backend/app/models/announcement.py`)로 추가한다.
- 관리자 전용 라우터(`/api/v1/admin/announcements`)로 공지 생성/목록/수정/삭제를 제공한다. 타겟은 `all`/`project`/`user` 3종(MVP, 그룹 타겟팅 제외).
- 사용자 라우터(`/api/v1/announcements`)는 `token_info`(user_id/project_id)로 서버 측에서 타겟팅을 직접 판별해 호출자에게 노출된 공지만 반환한다. 클라이언트가 보낸 타겟 필터는 신뢰하지 않는다(IDOR 방지). 읽음 처리·미읽음 카운트 포함.
- 대시보드 "시스템 알림" 카드에 관리자 공지와 쿼터 경고를 하나의 알림함으로 병합해 표시한다.
- 헤더 종 아이콘을 활성화(미읽음 배지 폴링 + 클릭 시 이동)하고, 신규 메시지함 페이지(`/dashboard/notifications`)와 관리자 발송 페이지(`/admin/announcements`)를 추가한다.
- 전달 방식은 기존 `autoRefresh.svelte.ts` 재사용 주기적 폴링으로 시작한다(SSE/Redis pub/sub는 후속).

## Non-goals
- 그룹(Keystone group) 대상 타겟팅 — Keystone 그룹 조회 캐싱 설계가 필요해 후속 작업으로 분리.
- SSE 실시간 푸시 및 레플리카 간 Redis pub/sub 팬아웃.
- DB 미설정 환경에서의 공지 영속 저장 폴백(Redis) — DB 필수 기능으로 명시, 미설정 시 관리자 발송 503 / 사용자 목록 빈 배열로 degrade.
