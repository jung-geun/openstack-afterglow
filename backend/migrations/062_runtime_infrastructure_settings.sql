-- Database-backed runtime infrastructure settings and immutable operation snapshots.
--
-- ResourcePolicy keeps the mutable administrator selection.  Long-running
-- operations persist the effective IDs and display metadata they resolved
-- before their first OpenStack side effect, so later policy changes cannot
-- change an in-flight operation.

CREATE TABLE IF NOT EXISTS runtime_settings (
    setting_key VARCHAR(100) NOT NULL,
    value_json JSON NOT NULL,
    updated_by_user_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE k3s_clusters
    ADD COLUMN IF NOT EXISTS server_image_id VARCHAR(128) NULL AFTER agent_flavor_id,
    ADD COLUMN IF NOT EXISTS resource_policy_snapshot JSON NULL AFTER template_snapshot;

ALTER TABLE layer_builds
    ADD COLUMN IF NOT EXISTS builder_flavor_id VARCHAR(128) NULL AFTER share_id,
    ADD COLUMN IF NOT EXISTS builder_network_id VARCHAR(128) NULL AFTER builder_flavor_id,
    ADD COLUMN IF NOT EXISTS resource_snapshot JSON NULL AFTER builder_network_id;

ALTER TABLE library_builds
    ADD COLUMN IF NOT EXISTS resource_snapshot JSON NULL AFTER cloud_init_status;

ALTER TABLE layer_import_jobs
    ADD COLUMN IF NOT EXISTS resource_snapshot JSON NULL AFTER build_ids;

ALTER TABLE layer_consumes
    ADD COLUMN IF NOT EXISTS resource_snapshot JSON NULL AFTER artifact_ids;

ALTER TABLE waygate_servers
    ADD COLUMN IF NOT EXISTS image_id VARCHAR(128) NULL AFTER flavor_id,
    ADD COLUMN IF NOT EXISTS floating_network_id VARCHAR(128) NULL AFTER provider_network_id,
    ADD COLUMN IF NOT EXISTS resource_policy_snapshot JSON NULL AFTER floating_network_id;
