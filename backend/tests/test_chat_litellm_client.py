"""litellm_client 토큰/비용 계산 + 스트리밍 usage 계측 폴백 단위 테스트.

litellm 의 로컬 계산(token_counter/cost_per_token)만 사용 — 네트워크 불요.
핵심 회귀 방지: 스트리밍이 usage 를 주지 않아도 과금이 0이 되지 않아야 한다.
"""

from app.services.chat import litellm_client

_MODEL = "gpt-3.5-turbo"  # litellm 내장 가격표에 존재하는 모델
_MESSAGES = [{"role": "user", "content": "안녕하세요, 오늘 날씨 어때요?"}]


class TestExtractUsage:
    def test_prefers_final_usage_dict(self):
        pt, ct = litellm_client.extract_usage(
            _MODEL, _MESSAGES, "맑습니다", {"prompt_tokens": 12, "completion_tokens": 3}
        )
        assert (pt, ct) == (12, 3)

    def test_prefers_final_usage_object(self):
        class _Usage:
            prompt_tokens = 20
            completion_tokens = 7

        pt, ct = litellm_client.extract_usage(_MODEL, _MESSAGES, "맑습니다", _Usage())
        assert (pt, ct) == (20, 7)

    def test_fallback_when_no_usage(self):
        # 스트리밍이 usage 를 주지 않은 경우(final_usage=None) → token_counter 폴백.
        pt, ct = litellm_client.extract_usage(_MODEL, _MESSAGES, "오늘은 맑고 따뜻합니다.", None)
        assert pt > 0
        assert ct > 0

    def test_fallback_when_usage_incomplete(self):
        # prompt_tokens 만 있고 completion_tokens 누락 → 폴백.
        pt, ct = litellm_client.extract_usage(_MODEL, _MESSAGES, "맑음", {"prompt_tokens": 5})
        assert pt > 0
        assert ct > 0


class TestCostFromUsage:
    def test_positive_cost_for_known_model(self):
        cost = litellm_client.cost_from_usage(_MODEL, prompt_tokens=1000, completion_tokens=1000)
        assert cost > 0

    def test_zero_tokens_zero_cost(self):
        cost = litellm_client.cost_from_usage(_MODEL, prompt_tokens=0, completion_tokens=0)
        assert cost == 0

    def test_unknown_model_returns_zero_not_raise(self):
        # 알 수 없는 모델은 예외 대신 0.0 반환(fail-soft) — 과금 로직이 죽지 않게.
        cost = litellm_client.cost_from_usage("no-such-model-xyz", prompt_tokens=100, completion_tokens=100)
        assert cost == 0.0


class TestCountTokens:
    def test_messages_positive(self):
        assert litellm_client.count_tokens(_MODEL, messages=_MESSAGES) > 0

    def test_text_positive(self):
        assert litellm_client.count_tokens(_MODEL, text="hello world") > 0
