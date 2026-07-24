"""refresh_runtime_settings 회귀 테스트.

버그 이력: refresh_runtime_settings 가 _SETTING_FIELDS 의 모든 필드를 무조건 DB 값(또는 "")으로
덮어써, DB 정책이 없으면 afterglow.conf 로 설정한 값(k3s 이미지·waygate provider/image 등)을
런타임에 폐기했다 → waygate 등 서비스가 설정돼도 site-config 게이트가 닫혀 사이드바에 미노출.
수정: DB 정책이 비어있으면 config/기본값을 유지하고, DB 에 값이 있을 때만 override 한다.
"""

from types import SimpleNamespace

import pytest

from app.services import resource_policy_store


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return _FakeResult(self._rows)


def _factory_returning(rows):
    def factory():
        return _FakeSession(rows)

    return factory


def _row(policy_key: str, resource_id):
    return SimpleNamespace(policy_key=policy_key, resource_id=resource_id)


@pytest.mark.asyncio
async def test_config_value_survives_when_no_db_policy(monkeypatch):
    """DB 정책이 없으면 config-file/기본값(waygate provider/image)이 유지되어야 한다."""
    from app.config import get_settings

    settings = get_settings()
    settings.waygate_provider_network_id = "config-net-uuid"
    settings.waygate_image_id = "config-img-uuid"

    monkeypatch.setattr(resource_policy_store, "_require_db", lambda: _factory_returning([]))
    await resource_policy_store.refresh_runtime_settings()

    assert settings.waygate_provider_network_id == "config-net-uuid"
    assert settings.waygate_image_id == "config-img-uuid"


@pytest.mark.asyncio
async def test_db_policy_overrides_config(monkeypatch):
    """DB 정책이 있으면 그것이 config 값을 override 한다."""
    from app.config import get_settings

    settings = get_settings()
    settings.waygate_provider_network_id = "config-net-uuid"

    rows = [_row("waygate.provider_network", "db-net-uuid")]
    monkeypatch.setattr(resource_policy_store, "_require_db", lambda: _factory_returning(rows))
    await resource_policy_store.refresh_runtime_settings()

    assert settings.waygate_provider_network_id == "db-net-uuid"


@pytest.mark.asyncio
async def test_cleared_db_policy_reverts_to_config(monkeypatch):
    """DB 정책이 명시적으로 비워지면(resource_id=None) config 기본값으로 복귀한다(blank 하지 않음)."""
    from app.config import get_settings

    settings = get_settings()
    settings.waygate_image_id = "config-img-uuid"

    rows = [_row("waygate.image", None)]
    monkeypatch.setattr(resource_policy_store, "_require_db", lambda: _factory_returning(rows))
    await resource_policy_store.refresh_runtime_settings()

    assert settings.waygate_image_id == "config-img-uuid"
