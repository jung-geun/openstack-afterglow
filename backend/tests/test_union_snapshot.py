"""Union 레이어 Manila Snapshot ↔ Union 결합 단위 테스트.

A10: POST /api/union/layers/{id}/snapshot — 레이어 Manila share 스냅샷 생성
      POST /api/union/layers/{id}/restore  — 레이어 Manila share 스냅샷 복원
"""

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import make_token_info

_NOW = datetime(2026, 4, 24, 0, 0, 0, tzinfo=UTC)


def _sha(seed: str) -> str:
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def _make_layer(layer_id: str, sealed: bool = True):
    from app.models.db import UnionLayer

    layer = MagicMock(spec=UnionLayer)
    layer.id = layer_id
    layer.name = "torch"
    layer.version = "2.4"
    layer.sealed = sealed
    layer.sealed_at = _NOW if sealed else None
    layer.parent_id = None
    return layer


@pytest.fixture
def admin_client():
    async def _override_token():
        return make_token_info(project_id="proj-admin", is_system_admin=True, roles=["admin"])

    from app.api.deps import get_token_info

    app.dependency_overrides[get_token_info] = _override_token
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(get_token_info, None)


# ---------------------------------------------------------------------------
# snapshot_layer 서비스 단위 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_layer_creates_manila_snapshot():
    """snapshot_layer: Manila create_share_snapshot 호출 + 결과 반환."""
    from app.models.union import SnapshotLayerRequest
    from app.services.union_layers import snapshot_layer

    layer = _make_layer(_sha("snap-src"))
    snap_result = {"id": "snap-1", "name": "union-layer-sha256:abc", "share_id": "share-x"}

    session = MagicMock()
    session.get = AsyncMock(return_value=layer)
    conn = MagicMock()

    req = SnapshotLayerRequest(share_id="share-x", name="my-snap")

    with patch("app.services.union_layers.manila.create_share_snapshot", return_value=snap_result) as mock_snap:
        result = await snapshot_layer(session, layer.id, req, conn)

    assert result == snap_result
    mock_snap.assert_called_once_with(conn, "share-x", "my-snap", None)


@pytest.mark.asyncio
async def test_snapshot_layer_auto_name():
    """name 미지정 시 layer_id 앞부분으로 자동 이름 생성."""
    from app.models.union import SnapshotLayerRequest
    from app.services.union_layers import snapshot_layer

    layer_id = _sha("snap-auto")
    layer = _make_layer(layer_id)
    session = MagicMock()
    session.get = AsyncMock(return_value=layer)
    conn = MagicMock()
    req = SnapshotLayerRequest(share_id="share-y")

    with patch("app.services.union_layers.manila.create_share_snapshot", return_value={}) as mock_snap:
        await snapshot_layer(session, layer_id, req, conn)

    called_name = mock_snap.call_args.args[2]
    assert called_name.startswith("union-layer-")


@pytest.mark.asyncio
async def test_snapshot_layer_missing_layer_raises():
    """레이어가 없으면 KeyError."""
    from app.models.union import SnapshotLayerRequest
    from app.services.union_layers import snapshot_layer

    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    conn = MagicMock()
    req = SnapshotLayerRequest(share_id="share-z")

    with pytest.raises(KeyError):
        await snapshot_layer(session, _sha("nonexistent"), req, conn)


# ---------------------------------------------------------------------------
# restore_layer 서비스 단위 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_layer_calls_revert():
    """restore_layer: Manila revert_to_snapshot 호출."""
    from app.models.union import RestoreLayerRequest
    from app.services.union_layers import restore_layer

    layer = _make_layer(_sha("restore-src"), sealed=False)
    session = MagicMock()
    session.get = AsyncMock(return_value=layer)
    conn = MagicMock()
    req = RestoreLayerRequest(share_id="share-r", snapshot_id="snap-r")

    with patch("app.services.union_layers.manila.revert_to_snapshot") as mock_revert:
        await restore_layer(session, layer.id, req, conn)

    mock_revert.assert_called_once_with(conn, "share-r", "snap-r")


@pytest.mark.asyncio
async def test_restore_layer_unseals_sealed_layer():
    """봉인된 레이어 복원 시 sealed=False로 재설정된다."""
    from app.models.union import RestoreLayerRequest
    from app.services.union_layers import restore_layer

    layer = _make_layer(_sha("restore-sealed"), sealed=True)
    session = MagicMock()
    session.get = AsyncMock(return_value=layer)
    session.commit = AsyncMock()
    conn = MagicMock()
    req = RestoreLayerRequest(share_id="share-s", snapshot_id="snap-s")

    with patch("app.services.union_layers.manila.revert_to_snapshot"):
        await restore_layer(session, layer.id, req, conn)

    assert layer.sealed is False
    assert layer.sealed_at is None
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_restore_layer_missing_layer_raises():
    """레이어가 없으면 KeyError."""
    from app.models.union import RestoreLayerRequest
    from app.services.union_layers import restore_layer

    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    conn = MagicMock()
    req = RestoreLayerRequest(share_id="share-x2", snapshot_id="snap-x2")

    with pytest.raises(KeyError):
        await restore_layer(session, _sha("missing"), req, conn)


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_api_returns_201(admin_client):
    """POST /api/union/layers/{id}/snapshot → 201."""
    from app.api.deps import get_os_conn
    from app.database import get_session

    layer_id = _sha("api-snap-src")
    snap_result = {"id": "snap-api-1", "share_id": "share-api"}

    mock_session = AsyncMock()
    mock_conn = MagicMock()

    async def override_session():
        yield mock_session

    async def override_conn():
        return mock_conn

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_os_conn] = override_conn
    try:
        with patch(
            "app.api.union.layers.union_layers.snapshot_layer",
            new_callable=AsyncMock,
            return_value=snap_result,
        ):
            resp = await admin_client.post(
                f"/api/v1/union/layers/{layer_id}/snapshot",
                json={"share_id": "share-api", "name": "test-snap"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_os_conn, None)

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_restore_api_returns_204(admin_client):
    """POST /api/union/layers/{id}/restore → 204."""
    from app.api.deps import get_os_conn
    from app.database import get_session

    layer_id = _sha("api-restore-src")
    mock_session = AsyncMock()
    mock_conn = MagicMock()

    async def override_session():
        yield mock_session

    async def override_conn():
        return mock_conn

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_os_conn] = override_conn
    try:
        with patch(
            "app.api.union.layers.union_layers.restore_layer",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await admin_client.post(
                f"/api/v1/union/layers/{layer_id}/restore",
                json={"share_id": "share-api", "snapshot_id": "snap-api"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_os_conn, None)

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_snapshot_api_layer_not_found_returns_404(admin_client):
    """존재하지 않는 레이어 스냅샷 → 404."""
    from app.api.deps import get_os_conn
    from app.database import get_session

    layer_id = _sha("api-snap-missing")
    mock_session = AsyncMock()
    mock_conn = MagicMock()

    async def override_session():
        yield mock_session

    async def override_conn():
        return mock_conn

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_os_conn] = override_conn
    try:
        with patch(
            "app.api.union.layers.union_layers.snapshot_layer",
            new_callable=AsyncMock,
            side_effect=KeyError("레이어를 찾을 수 없습니다"),
        ):
            resp = await admin_client.post(
                f"/api/v1/union/layers/{layer_id}/snapshot",
                json={"share_id": "share-api"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_os_conn, None)

    assert resp.status_code == 404
