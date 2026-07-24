-- 038_chat_mcp_encrypted_headers.sql
-- 원격 MCP 서버 인증 헤더(Bearer 토큰 / API key)를 암호화 저장.
--
-- 기존 headers(JSON, plaintext)는 하위호환용으로 계속 읽지만, 신규/수정 시에는
-- AES-256-GCM(도메인 llm_provider_key — encrypted_api_key 와 동일 마스터키) 으로
-- 암호화한 문자열을 encrypted_headers 에 저장한다.
-- 조회(API) 시 헤더 값은 마스킹되고, 실행 경로에서만 복호화된다.
-- 기존 행: NULL(암호화 헤더 없음 — 레거시 plaintext headers 로 폴백). 하위호환.

ALTER TABLE chat_mcp_servers
    ADD COLUMN encrypted_headers TEXT NULL AFTER headers;
