-- Durable, project-owned Glance image exports for the Palimpsest hub.
-- Source metadata is snapshotted before queueing; result_blob_digest is a soft
-- content-addressed reference because the same bytes may be reused across projects.

SET @tbl_exists := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'palimpsest_image_exports'
);
SET @ddl := IF(
  @tbl_exists = 0,
  'CREATE TABLE palimpsest_image_exports (
     id                        CHAR(36)     NOT NULL PRIMARY KEY,
     project_id                VARCHAR(64)  NOT NULL,
     created_by                VARCHAR(128) NULL,
     source_image_id           VARCHAR(64)  NOT NULL,
     source_name               VARCHAR(255) NOT NULL,
     source_disk_format        VARCHAR(16)  NOT NULL,
     source_size_bytes         BIGINT       NOT NULL,
     source_virtual_size_bytes BIGINT       NULL,
     source_checksum           VARCHAR(64)  NULL,
     source_hash_algo          VARCHAR(16)  NULL,
     source_hash_value         VARCHAR(128) NULL,
     source_updated_at         VARCHAR(64)  NULL,
     source_fingerprint        CHAR(64)     NOT NULL,
     artifact_key              CHAR(64)     NOT NULL,
     target_disk_format        VARCHAR(16)  NOT NULL,
     result_blob_digest        VARCHAR(71)  NULL,
     result_size_bytes         BIGINT       NULL,
     status                    VARCHAR(16)  NOT NULL DEFAULT ''queued'',
     progress_pct              INT          NOT NULL DEFAULT 0,
     error_code                VARCHAR(64)  NULL,
     error_message             TEXT         NULL,
     attempts                  INT          NOT NULL DEFAULT 0,
     next_at                   DATETIME(6)  NOT NULL,
     lease_owner               VARCHAR(128) NULL,
     lease_expires_at          DATETIME(6)  NULL,
     created_at                DATETIME(6)  NOT NULL,
     updated_at                DATETIME(6)  NOT NULL,
     started_at                DATETIME(6)  NULL,
     completed_at              DATETIME(6)  NULL,
     deleted_at                DATETIME(6)  NULL,
     UNIQUE KEY uq_palimpsest_exports_project_artifact (project_id, artifact_key),
     KEY idx_palimpsest_exports_artifact (artifact_key),
     KEY idx_palimpsest_exports_digest (result_blob_digest),
     KEY idx_palimpsest_exports_claim (status, next_at),
     KEY idx_palimpsest_exports_project_created (project_id, deleted_at, created_at)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4',
  'SELECT 1'
);
PREPARE palimpsest_image_exports_stmt FROM @ddl;
EXECUTE palimpsest_image_exports_stmt;
DEALLOCATE PREPARE palimpsest_image_exports_stmt;

-- create_all() may have materialized generic DATETIME columns before this
-- migration runs. Widen them idempotently so lease fences retain microseconds.
ALTER TABLE palimpsest_image_exports
  MODIFY next_at DATETIME(6) NOT NULL,
  MODIFY lease_expires_at DATETIME(6) NULL,
  MODIFY created_at DATETIME(6) NOT NULL,
  MODIFY updated_at DATETIME(6) NOT NULL,
  MODIFY started_at DATETIME(6) NULL,
  MODIFY completed_at DATETIME(6) NULL,
  MODIFY deleted_at DATETIME(6) NULL;
