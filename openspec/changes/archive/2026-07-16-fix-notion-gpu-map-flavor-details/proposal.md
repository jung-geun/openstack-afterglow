# Goal

Nova flavor metadata를 올바르게 해석해 Notion GPU map relation을 복구하고, exact GPU Spec title이 없으면 시스템 canonical GPU 이름을 등록해 연결한다.

# Scope

- `collect_instance_data()`의 embedded/상세 flavor 해석을 UUID와 이름 기반으로 보완한다.
- Missing-name GPU Spec upsert 계약을 회귀 테스트로 고정한다.

# Out of scope

- Notion schema 생성 또는 relation 조회 실패 시 보존 정책 변경
- GPU catalog alias 병합 규칙 변경
