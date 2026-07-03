-- Persist actual Glance image fingerprints for squashfs layer builds/artifacts
-- and track GitHub Dockerfile import jobs.

ALTER TABLE layer_builds
  ADD COLUMN base_image_id VARCHAR(128) DEFAULT NULL AFTER ubuntu_base,
  ADD COLUMN base_image_name VARCHAR(255) DEFAULT NULL AFTER base_image_id,
  ADD COLUMN base_image_checksum VARCHAR(128) DEFAULT NULL AFTER base_image_name,
  ADD COLUMN base_image_os_hash_algo VARCHAR(32) DEFAULT NULL AFTER base_image_checksum,
  ADD COLUMN base_image_os_hash_value VARCHAR(128) DEFAULT NULL AFTER base_image_os_hash_algo,
  ADD COLUMN base_image_min_disk INT DEFAULT NULL AFTER base_image_os_hash_value,
  ADD COLUMN base_image_visibility VARCHAR(32) DEFAULT NULL AFTER base_image_min_disk,
  ADD COLUMN base_image_owner VARCHAR(128) DEFAULT NULL AFTER base_image_visibility,
  ADD COLUMN source_metadata JSON DEFAULT NULL AFTER base_image_owner;

ALTER TABLE layer_artifacts
  ADD COLUMN base_image_id VARCHAR(128) DEFAULT NULL AFTER ubuntu_base,
  ADD COLUMN base_image_name VARCHAR(255) DEFAULT NULL AFTER base_image_id,
  ADD COLUMN base_image_checksum VARCHAR(128) DEFAULT NULL AFTER base_image_name,
  ADD COLUMN base_image_os_hash_algo VARCHAR(32) DEFAULT NULL AFTER base_image_checksum,
  ADD COLUMN base_image_os_hash_value VARCHAR(128) DEFAULT NULL AFTER base_image_os_hash_algo,
  ADD COLUMN base_image_min_disk INT DEFAULT NULL AFTER base_image_os_hash_value,
  ADD COLUMN base_image_visibility VARCHAR(32) DEFAULT NULL AFTER base_image_min_disk,
  ADD COLUMN base_image_owner VARCHAR(128) DEFAULT NULL AFTER base_image_visibility,
  ADD COLUMN source_metadata JSON DEFAULT NULL AFTER base_image_owner;

CREATE TABLE IF NOT EXISTS layer_import_jobs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_type VARCHAR(32) NOT NULL DEFAULT 'github_dockerfile',
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  progress_step VARCHAR(64) DEFAULT NULL,
  progress_pct INT NOT NULL DEFAULT 0,
  error_message TEXT DEFAULT NULL,
  github_url VARCHAR(512) NOT NULL,
  repo_owner VARCHAR(64) NOT NULL,
  repo_name VARCHAR(128) NOT NULL,
  commit_sha CHAR(40) NOT NULL,
  dockerfile_path VARCHAR(255) NOT NULL DEFAULT 'Dockerfile',
  layer_prefix VARCHAR(64) NOT NULL,
  profile_name VARCHAR(64) NOT NULL,
  ubuntu_base VARCHAR(255) NOT NULL,
  base_image_id VARCHAR(128) NOT NULL,
  base_image_name VARCHAR(255) DEFAULT NULL,
  base_image_checksum VARCHAR(128) DEFAULT NULL,
  base_image_os_hash_algo VARCHAR(32) DEFAULT NULL,
  base_image_os_hash_value VARCHAR(128) DEFAULT NULL,
  base_image_min_disk INT DEFAULT NULL,
  planned_layers JSON DEFAULT NULL,
  artifact_ids JSON DEFAULT NULL,
  build_ids JSON DEFAULT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6) DEFAULT NULL,
  KEY ix_layer_import_jobs_status (status),
  KEY ix_layer_import_jobs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
