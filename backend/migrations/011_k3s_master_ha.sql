-- Migration 011: k3s HA 멀티 마스터 지원
-- master_count: 1(기본) | 3 만 허용. ALTER 전 값이 없으므로 DEFAULT 1로 안전하게 추가.

ALTER TABLE k3s_clusters
    ADD COLUMN IF NOT EXISTS master_count INT NOT NULL DEFAULT 1;
