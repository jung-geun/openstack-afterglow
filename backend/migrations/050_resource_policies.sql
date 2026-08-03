-- Global administrator-managed OpenStack resource selection policies.
-- Resource IDs are discovered and validated against the live control plane; names
-- are retained only as display snapshots and are never used for provisioning.

CREATE TABLE resource_policies (
    policy_key VARCHAR(100) NOT NULL,
    resource_kind VARCHAR(32) NOT NULL,
    resource_id VARCHAR(128) NULL,
    resource_name VARCHAR(255) NULL,
    constraints JSON NULL,
    updated_by_user_id VARCHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (policy_key),
    KEY idx_resource_policies_kind (resource_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
