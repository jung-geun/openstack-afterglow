"""The retired standalone SDK repositories must never become dependency sources again."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_SERVICE_SDKS = ("drover", "lumen", "waygate")
_SOURCE_PATTERN = re.compile(
    r"^(?P<package>[a-z-]+) @ "
    r"git\+https://github\.com/openstack-afterglow/(?P<service>[a-z-]+)\.git@"
    r"(?P<revision>[0-9a-f]{40})#subdirectory=sdk$"
)
_LOCK_SOURCE_PATTERN = re.compile(
    r"^https://github\.com/openstack-afterglow/(?P<service>[a-z-]+)\.git\?"
    r"subdirectory=sdk&rev=(?P<revision>[0-9a-f]{40})#(?P=revision)$"
)


def _service_sdk_source(dependencies: list[str], package: str) -> str:
    matches = [dependency for dependency in dependencies if dependency.startswith(f"{package} @ ")]
    assert len(matches) == 1, f"expected exactly one source for {package}"
    return matches[0]


def test_service_sdks_only_resolve_from_their_own_service_repositories():
    backend_root = Path(__file__).resolve().parents[2]
    with (backend_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    dependency_sets = (
        pyproject["project"]["dependencies"],
        pyproject["dependency-groups"]["worker"],
    )
    for dependencies in dependency_sets:
        for service in _SERVICE_SDKS:
            package = f"{service}-sdk"
            source = _service_sdk_source(dependencies, package)
            match = _SOURCE_PATTERN.fullmatch(source)
            assert match, f"{package} must use its service repository sdk subdirectory"
            assert match["package"] == package
            assert match["service"] == service


def test_lockfile_preserves_the_service_owned_sdk_sources():
    backend_root = Path(__file__).resolve().parents[2]
    lockfile = tomllib.loads((backend_root / "uv.lock").read_text())
    locked_sources = {
        package["name"]: package["source"]["git"]
        for package in lockfile["package"]
        if package["name"] in {f"{service}-sdk" for service in _SERVICE_SDKS}
    }

    assert set(locked_sources) == {f"{service}-sdk" for service in _SERVICE_SDKS}
    for service in _SERVICE_SDKS:
        source = locked_sources[f"{service}-sdk"]
        match = _LOCK_SOURCE_PATTERN.fullmatch(source)
        assert match, f"{service}-sdk must be locked from its service repository"
        assert match["service"] == service
