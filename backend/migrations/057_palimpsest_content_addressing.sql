-- Palimpsest 콘텐츠 주소화 — layer_artifacts 에 digest 정체성 부여.
--
-- 배경: 운영 중인 squashfs 파이프라인의 LayerArtifact 는 int PK + parent_id(INT) +
-- sqsh_filename 으로만 식별되어 콘텐츠 해시가 없다. 이 상태로는
--   (a) 해시로 레이어 검색,
--   (b) 부모 체인을 추적해 한 번에 내려받기(OCI image-layout 번들),
--   (c) 동일 스택 재빌드 생략(빌드 캐시)
-- 가 전부 성립하지 않는다. 상세는 docs/palimpsest.md §3.
--
-- digest 규칙: `.sqsh` blob 바이트 자체의 sha256 (`sha256:<64hex>`).
-- union.md §3.3 의 결정적 tar 해시가 아니다 — 그 방식은 재현성을 노렸으나 union.md §6.4 가
-- 스스로 "재실행하면 해시가 달라진다"고 결론냈다. blob digest 는 기존 산출물에 백필 가능하고,
-- 다운로드 후 재계산만으로 검증되며, OCI blob digest 와 의미론이 같다.
--
-- blob_md5 는 외부 도구 호환용 **보조 검색 키**다. 식별·무결성의 권위는 언제나 sha256 이며
-- md5 를 보안 목적으로 사용하지 않는다.
--
-- blob_digest 에 UNIQUE 를 걸지 않는 이유: 같은 콘텐츠가 서로 다른 Manila share 에 존재할 수
-- 있다(레이어별 전용 share 구조). 중복 제거는 허브 계층의 책임이다.
--
-- 멱등(idempotent): 컬럼/인덱스가 이미 있으면 무시. MySQL/MariaDB 는 ADD COLUMN IF NOT EXISTS
-- 를 버전에 따라 지원하지 않으므로 information_schema 로 존재를 확인 후 분기한다.
--
-- ⚠ 배포 순서: 이 마이그레이션을 **먼저** 적용한 뒤 ORM 컬럼 추가를 배포한다. 반대로 하면
-- `Unknown column 'layer_artifacts.blob_digest'` 로 artifacts 엔드포인트가 즉시 500 이 된다
-- (waygate `waygate_servers.agent_token_encrypted` 전례).

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_artifacts'
    AND column_name = 'blob_digest'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE layer_artifacts
     ADD COLUMN blob_digest   VARCHAR(71) NULL AFTER size_bytes,
     ADD COLUMN blob_md5      CHAR(32)    NULL AFTER blob_digest,
     ADD COLUMN config_digest VARCHAR(71) NULL AFTER blob_md5,
     ADD COLUMN chain_id      VARCHAR(71) NULL AFTER config_digest,
     ADD COLUMN digest_state  VARCHAR(16) NOT NULL DEFAULT ''pending'' AFTER chain_id',
  'SELECT 1'
);
PREPARE palimpsest_digest_stmt FROM @ddl;
EXECUTE palimpsest_digest_stmt;
DEALLOCATE PREPARE palimpsest_digest_stmt;

SET @idx_digest_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_artifacts'
    AND index_name = 'idx_layer_artifacts_blob_digest'
);
SET @ddl := IF(
  @idx_digest_exists = 0,
  'ALTER TABLE layer_artifacts ADD KEY idx_layer_artifacts_blob_digest (blob_digest)',
  'SELECT 1'
);
PREPARE palimpsest_digest_idx_stmt FROM @ddl;
EXECUTE palimpsest_digest_idx_stmt;
DEALLOCATE PREPARE palimpsest_digest_idx_stmt;

SET @idx_chain_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_artifacts'
    AND index_name = 'idx_layer_artifacts_chain'
);
SET @ddl := IF(
  @idx_chain_exists = 0,
  'ALTER TABLE layer_artifacts ADD KEY idx_layer_artifacts_chain (chain_id)',
  'SELECT 1'
);
PREPARE palimpsest_chain_idx_stmt FROM @ddl;
EXECUTE palimpsest_chain_idx_stmt;
DEALLOCATE PREPARE palimpsest_chain_idx_stmt;
