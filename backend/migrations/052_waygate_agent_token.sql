-- Waygate 에이전트 reconcile 베어러 토큰을 durable 하게 보관.
--
-- 배경: 토큰은 프로비저닝 시 1회 발급되어 VM 에이전트가 15초마다 무기한 사용하는
-- 영구 제어채널 자격증명이다. 기존 구현은 Redis 에만 7일 TTL(setex)로 저장해,
-- (a) 7일 후 토큰 만료 → 모든 에이전트 호출 401 → 서버가 조용히 오프라인,
-- (b) Redis 재시작/eviction/maxmemory 시 재발급 경로 없이 제어채널 영구 소실
-- 이라는 결함이 있었다. 토큰을 AES-256-GCM(도메인 wg_agent_token) 암호화해 여기에
-- 저장하고 Redis 는 캐시로만 사용해 durable 하게 유지한다.
--
-- 멱등(idempotent): 컬럼이 이미 있으면 무시. MySQL/MariaDB 는 ADD COLUMN IF NOT EXISTS
-- 를 버전에 따라 지원하지 않으므로 존재 여부를 information_schema 로 확인 후 분기한다.

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'waygate_servers'
    AND column_name = 'agent_token_encrypted'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE waygate_servers ADD COLUMN agent_token_encrypted TEXT NULL AFTER key_name',
  'SELECT 1'
);
PREPARE waygate_agent_token_stmt FROM @ddl;
EXECUTE waygate_agent_token_stmt;
DEALLOCATE PREPARE waygate_agent_token_stmt;
