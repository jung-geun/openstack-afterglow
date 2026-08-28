"""Contracts test suite configuration."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Automatically mark all contract tests under tests/contracts/ with the contract marker."""
    for item in items:
        item.add_marker(pytest.mark.contract)
