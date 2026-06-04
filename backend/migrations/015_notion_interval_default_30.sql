-- Notion 동기화 기본 간격 5분 → 30분 변경 + 기존 행 갱신
-- 실행: mysql -u <user> -p <database> < 015_notion_interval_default_30.sql
-- auto_create_tables = true 환경에서는 앱 재시작 후 자동 적용됨

-- 컬럼 기본값 변경
-- (notion_config: 002 DDL로 생성, notion_targets: SQLAlchemy auto_create로 생성)
ALTER TABLE notion_config  MODIFY COLUMN interval_minutes INT NOT NULL DEFAULT 30;
ALTER TABLE notion_targets MODIFY COLUMN interval_minutes INT NOT NULL DEFAULT 30;

-- 기존에 기본값(5분)으로 남아있는 타겟/설정을 30분으로 상향
UPDATE notion_config  SET interval_minutes = 30 WHERE interval_minutes = 5;
UPDATE notion_targets SET interval_minutes = 30 WHERE interval_minutes = 5;
