from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.compute import CreateInstanceRequest
from app.services.instance_names import ensure_unique_instance_name, generate_instance_name


class _Compute:
    def __init__(self, names: list[str]):
        self._names = names

    def servers(self, *, details: bool = True):
        assert details is True
        return [SimpleNamespace(name=name) for name in self._names]


class _Conn:
    def __init__(self, names: list[str]):
        self.compute = _Compute(names)


def test_generated_instance_name_is_safe_slug() -> None:
    name = generate_instance_name()
    assert name == name.lower()
    assert len(name) <= 63
    assert name.replace("-", "").isalnum()


def test_empty_create_instance_name_is_accepted_for_server_side_generation() -> None:
    req = CreateInstanceRequest(name="", image_id="img-1", flavor_id="flavor-1")
    assert req.name is None


def test_requested_instance_name_rejects_duplicates_in_project() -> None:
    with pytest.raises(ValueError, match="이미 존재"):
        ensure_unique_instance_name(_Conn(["My-VM"]), "my-vm")


def test_empty_instance_name_generates_unique_project_name() -> None:
    generated = ensure_unique_instance_name(_Conn(["taken-vm"]), None)
    assert generated != "taken-vm"
    assert generated == generated.lower()
    assert len(generated) <= 63


def test_invalid_nonempty_instance_name_still_fails_validation() -> None:
    with pytest.raises(ValidationError):
        CreateInstanceRequest(name="bad name", image_id="img-1", flavor_id="flavor-1")
