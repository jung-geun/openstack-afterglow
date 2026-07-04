"""Layer workflow Ubuntu image mapping config tests."""

from __future__ import annotations

from app.config import Settings, _load_toml


def test_builder_ubuntu_image_mapping_loads_from_toml(monkeypatch):
    raw = {
        "builder": {
            "image_id": "legacy-builder",
            "ubuntu_18_04_image_id": "img-18",
            "ubuntu_20_04_image_id": "img-20",
            "ubuntu_22_04_image_id": "img-22",
            "ubuntu_24_04_image_id": "img-24",
        }
    }
    monkeypatch.setattr("app.config.load_raw_toml", lambda: raw)
    flat = _load_toml()
    assert flat["builder_ubuntu_18_04_image_id"] == "img-18"
    assert flat["builder_ubuntu_20_04_image_id"] == "img-20"
    assert flat["builder_ubuntu_22_04_image_id"] == "img-22"
    assert flat["builder_ubuntu_24_04_image_id"] == "img-24"


def test_settings_accepts_builder_ubuntu_image_mapping_fields():
    settings = Settings(
        builder_ubuntu_18_04_image_id="img-18",
        builder_ubuntu_20_04_image_id="img-20",
        builder_ubuntu_22_04_image_id="img-22",
        builder_ubuntu_24_04_image_id="img-24",
    )

    assert settings.builder_ubuntu_18_04_image_id == "img-18"
    assert settings.builder_ubuntu_20_04_image_id == "img-20"
    assert settings.builder_ubuntu_22_04_image_id == "img-22"
    assert settings.builder_ubuntu_24_04_image_id == "img-24"
