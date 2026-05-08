"""production + AFTERGLOW_ALLOW_INSECURE 결합 부팅 차단 검증.

`warn_insecure_defaults` model_validator 가 다음을 보장:
1) AFTERGLOW_ENV=production + AFTERGLOW_ALLOW_INSECURE=1 → 즉시 ValueError
2) AFTERGLOW_ENV=production + secret_key=default → ValueError
3) dev 환경 + INSECURE=1 + secret_key=default → 경고만 (부팅 허용)
"""

from __future__ import annotations

import importlib
import os

import pytest


def _build_settings_with_env(env: dict[str, str]):
    """get_settings 의 lru_cache 를 비우고, env 로 새 Settings 인스턴스 빌드."""
    from app import config as cfg

    saved = {k: os.environ.get(k) for k in env}
    try:
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(cfg)
        cfg.get_settings.cache_clear()
        return cfg.get_settings()
    finally:
        # 원본 env 복원
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(cfg)
        cfg.get_settings.cache_clear()


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
