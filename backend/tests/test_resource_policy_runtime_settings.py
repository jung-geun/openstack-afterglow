"""Database policy/runtime-setting authority regression tests."""

import pytest

from app.services import resource_policy_store


def test_policy_store_cannot_mutate_process_local_settings():
    assert not hasattr(resource_policy_store, "refresh_runtime_settings")
    assert not hasattr(resource_policy_store, "_SETTING_FIELDS")


def test_runtime_settings_are_strictly_allowlisted_and_typed():
    assert resource_policy_store._validate_runtime_value("notion.sync_enabled", False) is False

    with pytest.raises(resource_policy_store.RuntimeSettingValidationError):
        resource_policy_store._validate_runtime_value("notion.sync_enabled", 1)
    with pytest.raises(resource_policy_store.RuntimeSettingValidationError):
        resource_policy_store._validate_runtime_value("unknown", True)


def test_runtime_setting_registry_is_limited_to_afterglow_controls():
    assert set(resource_policy_store.RUNTIME_SETTING_SPECS) == {"notion.sync_enabled"}
