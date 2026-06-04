-- 014: Stampede 모드 (k3s 노드 오토스케일) 지원

ALTER TABLE k3s_clusters
    ADD COLUMN stampede_enabled TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE k3s_nodegroups
    ADD COLUMN stampede_enabled TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN min_size INT NOT NULL DEFAULT 0,
    ADD COLUMN max_size INT NOT NULL DEFAULT 5,
    ADD COLUMN stampede_state JSON NULL
    -- stampede_state: {last_scale_up, last_scale_down, consecutive_idle_checks, in_flight_count, in_flight_since}
;
