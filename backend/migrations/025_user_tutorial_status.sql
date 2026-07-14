-- 025_user_tutorial_status.sql
-- 사용자별 튜토리얼(투어) 진행 이력.
-- status: 'completed'(완주) | 'dismissed'(무시/패스). 기록이 없으면 미체험 → 프론트에서 강조.
-- (user_id, tour_id) 복합 PK 로 사용자·투어별 1행 upsert.

CREATE TABLE IF NOT EXISTS user_tutorial_statuses (
    user_id     VARCHAR(64)  NOT NULL,
    tour_id     VARCHAR(64)  NOT NULL,
    status      VARCHAR(16)  NOT NULL,
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    PRIMARY KEY (user_id, tour_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
