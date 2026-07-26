-- Palimpsest Dockerfile 빌드 확장 — 사용자 업로드(inline) 소스 + 빌드 캐시.
--
-- 배경: 기존 Dockerfile import 는 canonical public GitHub repo 에서 commit SHA 를 고정해
-- 받아오는 경로 하나뿐이었다(`layer_import_jobs.github_url`/`commit_sha` 등이 NOT NULL).
-- 사용자가 Dockerfile 본문을 직접 올리는 경로를 열려면 그 컬럼들이 비어 있을 수 있어야 한다.
-- `source_type` 컬럼은 이미 있었고(기본값 'github_dockerfile') 여기서 'inline_dockerfile' 을 쓴다.
--
-- 빌드 캐시: layer_artifacts.step_digest = sha256(부모 참조 + "\n" + 정규화된 instruction).
-- 같은 부모 위에 같은 명령을 다시 요청하면 기존 sealed artifact 를 재사용해 빌드를 건너뛴다.
-- Docker 의 레이어 캐시와 같은 개념이며 Palimpsest 의 chain_id 가 부모 참조를 제공한다.
--
-- 멱등: 컬럼 존재를 information_schema 로 확인 후 분기.

-- 1) layer_import_jobs — GitHub 전용 컬럼을 nullable 로 완화 + inline 원문 보관
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_import_jobs'
    AND column_name = 'dockerfile_text'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE layer_import_jobs
     MODIFY COLUMN github_url      VARCHAR(512) NULL,
     MODIFY COLUMN repo_owner      VARCHAR(64)  NULL,
     MODIFY COLUMN repo_name       VARCHAR(128) NULL,
     MODIFY COLUMN commit_sha      CHAR(40)     NULL,
     MODIFY COLUMN dockerfile_path VARCHAR(255) NULL,
     ADD COLUMN dockerfile_text   MEDIUMTEXT  NULL,
     ADD COLUMN dockerfile_digest VARCHAR(71) NULL,
     ADD COLUMN parent_digest     VARCHAR(71) NULL',
  'SELECT 1'
);
PREPARE palimpsest_inline_stmt FROM @ddl;
EXECUTE palimpsest_inline_stmt;
DEALLOCATE PREPARE palimpsest_inline_stmt;

-- 2) layer_artifacts — 빌드 캐시 키
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_artifacts'
    AND column_name = 'step_digest'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE layer_artifacts ADD COLUMN step_digest VARCHAR(71) NULL AFTER chain_id',
  'SELECT 1'
);
PREPARE palimpsest_step_digest_stmt FROM @ddl;
EXECUTE palimpsest_step_digest_stmt;
DEALLOCATE PREPARE palimpsest_step_digest_stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'layer_artifacts'
    AND index_name = 'idx_layer_artifacts_step_digest'
);
SET @ddl := IF(
  @idx_exists = 0,
  'ALTER TABLE layer_artifacts ADD KEY idx_layer_artifacts_step_digest (step_digest)',
  'SELECT 1'
);
PREPARE palimpsest_step_idx_stmt FROM @ddl;
EXECUTE palimpsest_step_idx_stmt;
DEALLOCATE PREPARE palimpsest_step_idx_stmt;
