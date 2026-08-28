## 구현

- [x] 비활성 Manila 배포에서 VM 생성 옵션 로더가 `/api/v1/file-storage`를 호출하지 않는다.
- [x] command palette가 section 서비스 조건을 route 항목에 상속한다.
- [x] VM async 생성의 배치 정책 검증 오류가 안전한 503으로 반환된다.
- [x] legacy importer가 Cinder 기본 availability zone 정책을 seed한다.

## 회귀 검증

- [x] Manila 활성/비활성 VM 옵션 로드 테스트를 추가한다.
- [x] command palette 서비스 필터 테스트를 추가한다.
- [x] VM async 사전검증 오류 응답 테스트를 추가한다.
- [x] importer Cinder AZ 수집 테스트를 추가한다.
- [x] exact selector와 관련 named target을 통과한다.
- [x] `npm run test:all`과 `npm run lint:backend`를 통과한다.
