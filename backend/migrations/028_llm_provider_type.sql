-- 028_llm_provider_type.sql
-- LLM 프로바이더에 provider_type 추가 — litellm custom_llm_provider 로 전달되어
-- openai(및 openai-호환)/anthropic/gemini/vertex_ai/azure/bedrock/ollama 등 각 API 형식을 결정한다.
-- 기존 행은 'openai'(가장 흔한 openai-호환) 기본값.

ALTER TABLE llm_providers
    ADD COLUMN provider_type VARCHAR(40) NOT NULL DEFAULT 'openai' AFTER name;
