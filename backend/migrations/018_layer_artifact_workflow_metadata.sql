-- 018: layer workflow metadata for stable parent selection and package display

ALTER TABLE layer_artifacts
    ADD COLUMN pip_packages JSON NULL AFTER python_version;

ALTER TABLE layer_builds
    ADD COLUMN pip_packages JSON NULL AFTER profile_name,
    ADD COLUMN parent_artifact_id INT NULL AFTER pip_packages,
    ADD CONSTRAINT fk_layer_builds_parent_artifact
        FOREIGN KEY (parent_artifact_id) REFERENCES layer_artifacts(id) ON DELETE SET NULL;
