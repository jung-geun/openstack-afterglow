-- PR 3-B: k3s 인증서 회전 추적 컬럼 추가
ALTER TABLE k3s_clusters
    ADD COLUMN last_rotation_at DATETIME NULL,
    ADD COLUMN last_rotation_initiated_by VARCHAR(64) NULL;
