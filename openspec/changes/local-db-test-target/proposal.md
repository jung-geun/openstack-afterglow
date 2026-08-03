# local-db-test-target

## Goal
로컬 MariaDB 테스트 프로필을 사용해 현재 DB 통합 테스트를 `db` target으로 실행할 수 있게 한다.

## Scope
- 존재하지 않는 과거 DB selector를 현재 `pytest.mark.db` 테스트로 교체한다.
- Docker Compose test profile을 자동 기동하는 `npm run test:db` 명령을 제공한다.
- DB 테스트 문서와 dev 브랜치 CI selector를 현재 target과 동기화한다.
- 일반 unit/full gate는 로컬 MariaDB를 암묵적으로 요구하지 않는다.
