-- 032_chat_model_pricing.sql
-- 관리자 검토형 models.dev 기본 단가와 불변 채팅 사용량 가격 스냅샷.
-- llm_models.input_price/output_price 는 계속 USD per token (DECIMAL(20,10))이다.

ALTER TABLE llm_providers
    ADD COLUMN models_dev_provider_id VARCHAR(100) NULL AFTER margin_multiplier;

ALTER TABLE llm_models
    ADD COLUMN models_dev_model_id VARCHAR(190) NULL AFTER output_price,
    ADD COLUMN price_source VARCHAR(20) NULL AFTER models_dev_model_id,
    ADD COLUMN price_metadata JSON NULL AFTER price_source,
    ADD CONSTRAINT chk_llm_models_price_source
        CHECK (price_source IS NULL OR price_source IN ('manual', 'models.dev'));

UPDATE llm_models
SET price_source = 'manual'
WHERE (input_price IS NOT NULL OR output_price IS NOT NULL)
  AND price_source IS NULL;

ALTER TABLE chat_usage_logs
    ADD COLUMN event_id VARCHAR(64) NULL AFTER api_key_id,
    ADD COLUMN pricing_status VARCHAR(20) NOT NULL DEFAULT 'legacy' AFTER event_id,
    ADD COLUMN pricing_snapshot JSON NULL AFTER pricing_status,
    ADD UNIQUE KEY uq_chat_usage_logs_event_id (event_id),
    ADD CONSTRAINT chk_chat_usage_logs_pricing_status
        CHECK (pricing_status IN ('legacy', 'priced', 'partial', 'unpriced'));
