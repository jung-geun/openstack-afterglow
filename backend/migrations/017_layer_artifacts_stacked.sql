-- 017: layer_artifacts 스태킹 지원 컬럼 추가 (parent_id, is_sealed)

ALTER TABLE layer_artifacts
    ADD COLUMN parent_id INT NULL AFTER build_id,
    ADD COLUMN is_sealed TINYINT(1) NOT NULL DEFAULT 0 AFTER parent_id,
    ADD CONSTRAINT fk_layer_artifacts_parent
        FOREIGN KEY (parent_id) REFERENCES layer_artifacts(id) ON DELETE SET NULL;
