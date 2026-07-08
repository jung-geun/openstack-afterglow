-- DB-backed public branding assets for login-page logo variants.
-- Content is validated before insertion and capped at 1 MiB by application code.

CREATE TABLE IF NOT EXISTS site_branding_assets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  slot VARCHAR(32) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(64) NOT NULL,
  size_bytes INT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  content MEDIUMBLOB NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  updated_by_user_id VARCHAR(64) DEFAULT NULL,
  UNIQUE KEY uq_site_branding_assets_slot (slot),
  KEY ix_site_branding_assets_slot (slot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
