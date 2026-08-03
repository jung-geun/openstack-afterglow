"""Legacy layer image selectors are no longer runtime configuration."""

from __future__ import annotations

import tomllib
from pathlib import Path

from app.config import Settings, _load_toml


def test_builder_image_selectors_are_not_loaded_from_toml(monkeypatch):
    monkeypatch.setattr(
        "app.config.load_raw_toml",
        lambda: {"builder": {"image_id": "legacy", "ubuntu_24_04_image_id": "img-24"}},
    )

    flat = _load_toml()

    assert "builder_image_id" not in flat
    assert "builder_ubuntu_24_04_image_id" not in flat


def test_settings_excludes_legacy_builder_image_fields():
    assert "builder_image_id" not in Settings.model_fields
    assert "builder_ubuntu_24_04_image_id" not in Settings.model_fields


def test_afterglow_conf_example_keeps_builder_settings_in_builder_table():
    root = Path(__file__).resolve().parents[2]
    with (root / "afterglow.conf.example").open("rb") as config_file:
        parsed = tomllib.load(config_file)

    assert parsed["builder"]["build_timeout"] == 3600
    assert parsed["builder"]["layer_share_size_gb"] == 20
