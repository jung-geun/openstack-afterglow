-- PR 2A: k3s Nodegroup 추상화 레이어
-- k3s_nodegroups: 클러스터 내 노드 그룹 (server / agent 역할 분리)
-- k3s_nodegroup_vms: 노드그룹별 VM 추적 (기존 k3s_agent_vms 대응)

CREATE TABLE IF NOT EXISTS k3s_nodegroups (
    id          CHAR(36)      NOT NULL,
    cluster_id  CHAR(36)      NOT NULL,
    name        VARCHAR(63)   NOT NULL,
    role        VARCHAR(10)   NOT NULL DEFAULT 'agent',  -- 'server' | 'agent'
    node_count  INT           NOT NULL DEFAULT 0,
    flavor_id   VARCHAR(64)   DEFAULT NULL,
    image_id    VARCHAR(64)   DEFAULT NULL,
    labels      JSON          DEFAULT NULL,
    taints      JSON          DEFAULT NULL,
    is_default  TINYINT(1)    NOT NULL DEFAULT 0,        -- 1 = 마이그레이션 생성 기본 그룹
    created_at  DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at  DATETIME(6)   DEFAULT NULL,
    PRIMARY KEY (id),
    INDEX idx_ng_cluster (cluster_id),
    INDEX idx_ng_cluster_role (cluster_id, role),
    CONSTRAINT fk_ng_cluster FOREIGN KEY (cluster_id) REFERENCES k3s_clusters (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


CREATE TABLE IF NOT EXISTS k3s_nodegroup_vms (
    id           INT           NOT NULL AUTO_INCREMENT,
    nodegroup_id CHAR(36)      NOT NULL,
    cluster_id   CHAR(36)      NOT NULL,
    vm_id        VARCHAR(64)   NOT NULL,
    name         VARCHAR(255)  DEFAULT NULL,
    status       VARCHAR(20)   NOT NULL DEFAULT 'CREATING',
    created_at   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    INDEX idx_ngvm_nodegroup (nodegroup_id),
    INDEX idx_ngvm_cluster (cluster_id),
    INDEX idx_ngvm_vm (vm_id),
    CONSTRAINT fk_ngvm_nodegroup FOREIGN KEY (nodegroup_id) REFERENCES k3s_nodegroups (id) ON DELETE CASCADE,
    CONSTRAINT fk_ngvm_cluster   FOREIGN KEY (cluster_id)   REFERENCES k3s_clusters (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ---------------------------------------------------------------------------
-- 기존 클러스터 백필: default-server + default-agent 노드그룹 생성
-- 이미 존재하는 클러스터(deleted 포함)에 대해 실행하며 멱등 보장
-- ---------------------------------------------------------------------------

-- default-server nodegroup (각 클러스터당 1개, node_count=1, is_default=1)
INSERT INTO k3s_nodegroups (id, cluster_id, name, role, node_count, flavor_id, is_default, created_at, updated_at)
SELECT
    -- UUID v4 대신 결정론적 CHAR(36) — 클러스터 id 기반 접두사
    CONCAT(LEFT(c.id, 8), '-0000-4000-8000-000000000001') AS id,
    c.id                AS cluster_id,
    'default-server'    AS name,
    'server'            AS role,
    1                   AS node_count,
    c.server_flavor_id  AS flavor_id,
    1                   AS is_default,
    c.created_at,
    c.updated_at
FROM k3s_clusters c
WHERE NOT EXISTS (
    SELECT 1 FROM k3s_nodegroups ng
    WHERE ng.cluster_id = c.id AND ng.name = 'default-server'
);

-- default-agent nodegroup (각 클러스터당 1개, node_count=agent_count, is_default=1)
INSERT INTO k3s_nodegroups (id, cluster_id, name, role, node_count, flavor_id, is_default, created_at, updated_at)
SELECT
    CONCAT(LEFT(c.id, 8), '-0000-4000-8000-000000000002') AS id,
    c.id                AS cluster_id,
    'default-agent'     AS name,
    'agent'             AS role,
    c.agent_count       AS node_count,
    c.agent_flavor_id   AS flavor_id,
    1                   AS is_default,
    c.created_at,
    c.updated_at
FROM k3s_clusters c
WHERE NOT EXISTS (
    SELECT 1 FROM k3s_nodegroups ng
    WHERE ng.cluster_id = c.id AND ng.name = 'default-agent'
);

-- k3s_agent_vms → k3s_nodegroup_vms 마이그레이션
-- default-agent nodegroup id를 JOIN으로 매핑
INSERT INTO k3s_nodegroup_vms (nodegroup_id, cluster_id, vm_id, name, status, created_at)
SELECT
    ng.id   AS nodegroup_id,
    av.cluster_id,
    av.vm_id,
    av.name,
    av.status,
    av.created_at
FROM k3s_agent_vms av
JOIN k3s_nodegroups ng ON ng.cluster_id = av.cluster_id AND ng.name = 'default-agent'
WHERE NOT EXISTS (
    SELECT 1 FROM k3s_nodegroup_vms nv
    WHERE nv.cluster_id = av.cluster_id AND nv.vm_id = av.vm_id
);
