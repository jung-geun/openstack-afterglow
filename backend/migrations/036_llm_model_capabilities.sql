-- 036_llm_model_capabilities.sql
-- 모델 능력(capabilities) 저장 + 자동 메모리 모델 플래그.
--
-- capabilities(JSON): {vision, reasoning, tool_call, attachment, modalities{input,output},
--   reasoning_options, context_limit}. NULL 이면 런타임 litellm 판별로 fallback.
-- capability_source: 'override'(관리자 수동) | 'models_dev'(import) | NULL.
-- is_memory_model: 채팅 후 사용자 메모리 자동 추출용 초소형 모델(최대 1개, is_title_model 과 동일 패턴).
-- 기존 행: capabilities NULL(litellm fallback), is_memory_model 0. 하위호환.

ALTER TABLE llm_models
    ADD COLUMN is_memory_model TINYINT(1) NOT NULL DEFAULT 0 AFTER is_title_model,
    ADD COLUMN capabilities JSON NULL AFTER price_metadata,
    ADD COLUMN capability_source VARCHAR(20) NULL AFTER capabilities;
