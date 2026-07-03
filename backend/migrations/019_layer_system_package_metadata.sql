-- 019: apt-installable system package metadata for admin layer builds
ALTER TABLE layer_builds
  ADD COLUMN apt_packages JSON NULL AFTER pip_packages;

ALTER TABLE layer_artifacts
  ADD COLUMN apt_packages JSON NULL AFTER pip_packages;
