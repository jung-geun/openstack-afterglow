-- 020: Ubuntu base compatibility metadata for admin layer builds
ALTER TABLE layer_builds
  ADD COLUMN ubuntu_base VARCHAR(255) NOT NULL DEFAULT 'ubuntu-24.04-server-2026-04-15' AFTER apt_packages;

ALTER TABLE layer_artifacts
  ADD COLUMN ubuntu_base VARCHAR(255) NOT NULL DEFAULT 'ubuntu-24.04-server-2026-04-15' AFTER apt_packages;
