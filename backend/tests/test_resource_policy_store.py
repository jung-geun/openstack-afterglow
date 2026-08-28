from unittest.mock import AsyncMock, patch

import pytest

from app.services.resource_policies import ResourcePolicyValidationError
from app.services.resource_policy_store import resolve_policy_snapshot


@pytest.mark.asyncio
async def test_resolve_policy_snapshot_reports_both_missing_placement_policies():
    mock_get_policy_snapshot = AsyncMock(
        return_value={
            "nova.default_compute_availability_zone": None,
            "cinder.default_volume_availability_zone": None,
        }
    )
    mock_validate_existing_selection = AsyncMock()

    conn = object()
    keys = (
        "nova.default_compute_availability_zone",
        "cinder.default_volume_availability_zone",
    )

    with (
        patch(
            "app.services.resource_policy_store.get_policy_snapshot",
            mock_get_policy_snapshot,
        ),
        patch(
            "app.services.resource_policy_store.validate_existing_selection",
            mock_validate_existing_selection,
        ),
    ):
        with pytest.raises(ResourcePolicyValidationError) as exc_info:
            await resolve_policy_snapshot(conn=conn, keys=keys)

    assert (
        str(exc_info.value)
        == "required resource policies are not configured: nova.default_compute_availability_zone, cinder.default_volume_availability_zone"
    )
    mock_get_policy_snapshot.assert_awaited_once_with(keys)
    mock_validate_existing_selection.assert_not_called()
