-- Public squashfs publication gates and caller-owned consume tracking.
-- Existing rows stay private by default. Admin-created consume rows remain project_id NULL.

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_consumes' AND COLUMN_NAME = 'project_id') = 0,
  'ALTER TABLE layer_consumes ADD COLUMN project_id VARCHAR(64) DEFAULT NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_consumes' AND COLUMN_NAME = 'artifact_ids') = 0,
  'ALTER TABLE layer_consumes ADD COLUMN artifact_ids JSON DEFAULT NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_consumes' AND INDEX_NAME = 'ix_layer_consumes_project_id') = 0,
  'CREATE INDEX ix_layer_consumes_project_id ON layer_consumes (project_id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_artifacts' AND COLUMN_NAME = 'is_published') = 0,
  'ALTER TABLE layer_artifacts ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_artifacts' AND INDEX_NAME = 'ix_layer_artifacts_is_published') = 0,
  'CREATE INDEX ix_layer_artifacts_is_published ON layer_artifacts (is_published)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_profiles' AND COLUMN_NAME = 'is_published') = 0,
  'ALTER TABLE layer_profiles ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT FALSE',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'layer_profiles' AND INDEX_NAME = 'ix_layer_profiles_is_published') = 0,
  'CREATE INDEX ix_layer_profiles_is_published ON layer_profiles (is_published)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
