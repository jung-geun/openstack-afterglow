import importlib.util
from pathlib import Path

import pytest

_VALIDATOR_PATH = Path(__file__).resolve().parents[2] / "deploy/kolla/ansible/roles/waygate/files/validate_image_ref.py"
_SPEC = importlib.util.spec_from_file_location("kolla_waygate_image_ref", _VALIDATOR_PATH)
assert _SPEC and _SPEC.loader
_VALIDATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_VALIDATOR)


def test_accepts_canonical_remote_digest_reference() -> None:
    _VALIDATOR.validate_image_ref(
        "ghcr.io/openstack-afterglow/waygate-worker@sha256:"
        "52a69c5349141677163a8fbaf5c1dacad03fdbb4d2b2d9b30c1c4b1a9cacb235",
        source_mode=False,
    )


def test_rejects_truncated_remote_digest() -> None:
    with pytest.raises(ValueError, match="64-lowercase-hex"):
        _VALIDATOR.validate_image_ref(
            "ghcr.io/openstack-afterglow/waygate-worker@sha256:"
            "52a69c5349141677163a8fbaf5c1dacad03fdbb4d2d9b30c1c4b1a9cacb235",
            source_mode=False,
        )


def test_rejects_mutable_remote_tag() -> None:
    with pytest.raises(ValueError, match="64-lowercase-hex"):
        _VALIDATOR.validate_image_ref(
            "ghcr.io/openstack-afterglow/waygate-worker:dev",
            source_mode=False,
        )


def test_accepts_source_build_commit_tag() -> None:
    _VALIDATOR.validate_image_ref(
        "afterglow-local/waygate-api:e83ce559e3e3",
        source_mode=True,
    )
