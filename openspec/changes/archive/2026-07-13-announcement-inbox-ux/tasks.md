# Tasks

- [x] 사용자용 공지 응답에 발송자/게시·만료 시각 필드 추가 (`_serialize_user`, `AnnouncementUserResponse`)
- [x] 사용자 페이로드 필드 계약 테스트 추가 (`test_announcements.py` 직렬화 단위 테스트 + `test_announcements_db.py` 필드 검증 — 일회용 MariaDB로 13건 통과 확인)
- [x] `AnnouncementUser` 프론트 타입 확장
- [x] 대시보드 "시스템 알림" 카드 공지 제목 → 알림함 딥링크(`?focus=<id>`)로 변경
- [x] 헤더 종 아이콘 드롭다운(최근 공지 목록 + "전체 알림 보기") 구현
- [x] 알림함 공지 펼침 상세(본문 + 발송자·발송/게시·만료 시각) + `?focus=` 자동 펼침/스크롤 구현
- [x] 적대적 리뷰 워크플로(3렌즈 × 검증) 확정 발견 5건 수정: ①`?focus=` 대상이 스테일 목록에 없으면 1회 재조회 ②동일 `?focus=` 재탐색 재펼침(`afterNavigate` 전환) ③Escape 시 종 버튼 포커스 복귀 ④모바일 바텀 시트(ProjectSelector 패턴) ⑤`created_by_user_id`(Keystone 내부 UUID) 사용자 노출 제거
- [x] `npm run test:all` + `npm run lint:backend` 통과 후 커밋 — 동시 세션(튜토리얼)의 실패 3건 해소를 폴링으로 대기한 뒤 전체 green(frontend 466/466, backend 전체, ruff) 확인. `+layout.svelte`는 Tutorial hunk를 제외한 외과적 스테이징(`git apply --cached`)으로 커밋.
