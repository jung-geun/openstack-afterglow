-- Palimpsest 허브 — 레이어를 digest 로 저장·검색·배포하는 레지스트리.
--
-- 목적: 레이어를 직접 만들어 업로드하거나, 기존 레이어를 선택적으로 가져오고, md5/해시로 검색하며,
-- 부모 체인을 추적해 한 번에 내려받는다(OCI image-layout 번들). 설계는 docs/palimpsest.md.
--
-- 왜 `layer_artifacts` 를 그대로 쓰지 않는가:
--   layer_artifacts 는 **이 사이트에서 빌드된** 레이어이고 Manila share 에 산출물이 있다.
--   허브 항목은 외부에서 업로드·import 될 수 있고 blob 은 허브 blob store 가 소유한다.
--   두 관심사가 다르므로 테이블을 분리하고, 로컬 artifact → 허브는 publish 로 연결한다.
--
-- 부모 참조가 FK 가 아닌 이유: 부모가 자식보다 늦게 업로드될 수 있고(또는 영영 안 올 수 있고),
-- 번들 import 는 순서를 보장하지 않는다. digest 로 느슨하게 참조하고 조회 시 해석한다.

SET @tbl_exists := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'palimpsest_hub_layers'
);
SET @ddl := IF(
  @tbl_exists = 0,
  'CREATE TABLE palimpsest_hub_layers (
     id             INT AUTO_INCREMENT PRIMARY KEY,
     blob_digest    VARCHAR(71)  NOT NULL,
     blob_md5       CHAR(32)     NULL,
     size_bytes     BIGINT       NOT NULL,
     media_type     VARCHAR(128) NOT NULL,
     config_digest  VARCHAR(71)  NOT NULL,
     chain_id       VARCHAR(71)  NULL,
     parent_digest  VARCHAR(71)  NULL,
     name           VARCHAR(64)  NOT NULL,
     kind           VARCHAR(16)  NOT NULL,
     ubuntu_base    VARCHAR(64)  NULL,
     python_version VARCHAR(16)  NULL,
     config_json    JSON         NOT NULL,
     project_id     VARCHAR(64)  NULL,
     is_published   TINYINT(1)   NOT NULL DEFAULT 0,
     created_by     VARCHAR(128) NULL,
     created_at     DATETIME(6)  NOT NULL,
     UNIQUE KEY uq_palimpsest_hub_layers_digest (blob_digest),
     KEY idx_palimpsest_hub_layers_chain (chain_id),
     KEY idx_palimpsest_hub_layers_parent (parent_digest),
     KEY idx_palimpsest_hub_layers_name (name),
     KEY idx_palimpsest_hub_layers_md5 (blob_md5),
     KEY idx_palimpsest_hub_layers_project (project_id)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4',
  'SELECT 1'
);
PREPARE palimpsest_hub_layers_stmt FROM @ddl;
EXECUTE palimpsest_hub_layers_stmt;
DEALLOCATE PREPARE palimpsest_hub_layers_stmt;

-- 업로드 세션. OCI Distribution 의 blob upload(POST/PATCH/PUT)를 `/v2/` 없이 차용한다 —
-- 중단 후 재개가 가능하고 구현자에게 익숙하다.
SET @tbl_exists := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'palimpsest_hub_uploads'
);
SET @ddl := IF(
  @tbl_exists = 0,
  'CREATE TABLE palimpsest_hub_uploads (
     id              CHAR(32)     NOT NULL PRIMARY KEY,
     declared_digest VARCHAR(71)  NULL,
     received_bytes  BIGINT       NOT NULL DEFAULT 0,
     project_id      VARCHAR(64)  NULL,
     created_by      VARCHAR(128) NULL,
     created_at      DATETIME(6)  NOT NULL,
     updated_at      DATETIME(6)  NOT NULL,
     KEY idx_palimpsest_hub_uploads_created (created_at),
     KEY idx_palimpsest_hub_uploads_project (project_id)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4',
  'SELECT 1'
);
PREPARE palimpsest_hub_uploads_stmt FROM @ddl;
EXECUTE palimpsest_hub_uploads_stmt;
DEALLOCATE PREPARE palimpsest_hub_uploads_stmt;
