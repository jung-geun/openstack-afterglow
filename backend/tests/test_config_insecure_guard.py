"""production + AFTERGLOW_ALLOW_INSECURE 결합 부팅 차단 검증.

`warn_insecure_defaults` model_validator 가 다음을 보장:
1) AFTERGLOW_ENV=production + AFTERGLOW_ALLOW_INSECURE=1 → 즉시 ValueError
2) AFTERGLOW_ENV=production + secret_key=default → ValueError
3) dev 환경 + INSECURE=1 + secret_key=default → 경고만 (부팅 허용)
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def _build_settings_with_env(env: dict[str, str]):
    """env 로 Settings 클래스를 직접 instantiate. importlib.reload 는 다른 테스트에
    누수되므로 사용하지 않고, 환경변수만 patch.dict 로 격리한다.
    """
    from app.config import Settings

    # env 안의 None 은 변수 삭제 의미
    target_env = {k: v for k, v in env.items() if v is not None}
    clear_env = [k for k, v in env.items() if v is None]
    with patch.dict(os.environ, target_env, clear=False):
        # 명시적 None 삭제
        for k in clear_env:
            os.environ.pop(k, None)
        return Settings()


def test_production_with_insecure_flag_fails_fast():
    """AFTERGLOW_ENV=production + AFTERGLOW_ALLOW_INSECURE=1 → ValueError."""
    with pytest.raises(ValueError, match="AFTERGLOW_ALLOW_INSECURE=1 must NOT be set"):
        _build_settings_with_env(
            {
                "AFTERGLOW_ENV": "production",
                "AFTERGLOW_ALLOW_INSECURE": "1",
                # secret_key 는 default 든 아니든 INSECURE 자체로 거부
                "SECRET_KEY": "real-strong-key-1234567890",
            }
        )


def test_production_with_default_secret_fails_fast():
    """AFTERGLOW_ENV=production + secret_key=default → ValueError."""
    with pytest.raises(ValueError, match="while AFTERGLOW_ENV=production"):
        _build_settings_with_env(
            {
                "AFTERGLOW_ENV": "production",
                "AFTERGLOW_ALLOW_INSECURE": "",
                "SECRET_KEY": "change-me-in-production",
            }
        )


def test_development_with_insecure_flag_succeeds():
    """dev 환경에서는 INSECURE=1 + default secret 가 경고만 — 부팅 허용."""
    settings = _build_settings_with_env(
        {
            "AFTERGLOW_ENV": "development",
            "AFTERGLOW_ALLOW_INSECURE": "1",
            "SECRET_KEY": "change-me-in-production",
        }
    )
    assert settings.secret_key == "change-me-in-production"


def test_development_without_insecure_or_real_key_fails():
    """dev 환경이라도 INSECURE 미설정 + default secret 이면 거부."""
    with pytest.raises(ValueError, match="default value"):
        _build_settings_with_env(
            {
                "AFTERGLOW_ENV": "development",
                "AFTERGLOW_ALLOW_INSECURE": "",
                "SECRET_KEY": "change-me-in-production",
            }
        )
