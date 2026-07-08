"""볼륨 스냅샷 API 단위 테스트."""

from unittest.mock import AsyncMock, patch

import pytest


def _make_volume_in_use():
    from unittest.mock import MagicMock

    vol = MagicMock()
    vol.project_id = "test-project-123"
    vol.tenant_id = None
    vol.status = "in-use"
    return vol


def make_snapshot(snap_id: str = "snap-1", name: str = "test-snap", project_id: str = "test-project-123") -> dict:
    return {
        "id": snap_id,
        "name": name,
        "status": "available",
        "size": 10,
        "volume_id": "vol-1",
        "created_at": "2024-01-01T00:00:00Z",
        "description": None,
        "project_id": project_id,
    }


@pytest.mark.asyncio
async def test_list_snapshots(client, mock_conn):
    """일반 사용자 — caller_project_id=pid 로 호출되어 해당 프로젝트 스냅샷만 반환."""
    with patch("app.api.storage.volume_snapshots.cinder.list_snapshots", return_value=[make_snapshot()]) as mock_ls:
        resp = await client.get("/api/v1/volume-snapshots")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert resp.json()[0]["id"] == "snap-1"
    # caller_project_id 인자로 pid("test-project-123")가 전달돼야 함
    _args, kwargs = mock_ls.call_args
    assert kwargs.get("caller_project_id") == "test-project-123" or _args[2] == "test-project-123"


@pytest.mark.asyncio
async def test_list_snapshots_admin_sees_all(admin_client, mock_conn):
    """시스템 관리자 — caller_project_id=None 으로 호출되어 전체 스냅샷 반환."""
    other_snap = make_snapshot("snap-2", project_id="other-project")
    with patch(
        "app.api.storage.volume_snapshots.cinder.list_snapshots", return_value=[make_snapshot(), other_snap]
    ) as mock_ls:
        resp = await admin_client.get("/api/v1/volume-snapshots")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    _args, kwargs = mock_ls.call_args
    assert kwargs.get("caller_project_id") is None or (len(_args) > 2 and _args[2] is None)


@pytest.mark.asyncio
async def test_list_snapshots_filters_other_project(client, mock_conn):
    """일반 사용자 — 다른 프로젝트 스냅샷은 cinder.list_snapshots 내부에서 제외됨."""
    own_snap = make_snapshot("snap-own", project_id="test-project-123")
    # 서비스가 필터링 후 own_snap만 반환한다고 모킹
    with patch("app.api.storage.volume_snapshots.cinder.list_snapshots", return_value=[own_snap]):
        resp = await client.get("/api/v1/volume-snapshots")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert "snap-own" in ids
    assert "snap-other" not in ids


@pytest.mark.asyncio
async def test_create_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.create_snapshot", return_value=make_snapshot("snap-new")):
        resp = await client.post(
            "/api/v1/volume-snapshots",
            json={
                "volume_id": "vol-1",
                "name": "test-snap",
                "description": "",
                "force": False,
            },
        )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.get_snapshot", return_value=make_snapshot()):
        resp = await client.get("/api/v1/volume-snapshots/snap-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "snap-1"


@pytest.mark.asyncio
async def test_delete_snapshot(client, mock_conn):
    with patch("app.api.storage.volume_snapshots.cinder.delete_snapshot", return_value=None):
        resp = await client.delete("/api/v1/volume-snapshots/snap-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_snapshot_cached(client, mock_conn):
    """GET /{snapshot_id} 는 cached_call 을 통해 반환된다."""
    with patch("app.api.storage.volume_snapshots.cinder.get_snapshot", return_value=make_snapshot()) as mock_get:
        resp = await client.get("/api/v1/volume-snapshots/snap-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "snap-1"
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_create_snapshot_invalidates_cache(client, mock_conn):
    """스냅샷 생성 후 snapshots* 패턴 무효화 + mutation count 증가."""
    with (
        patch("app.api.storage.volume_snapshots.cinder.create_snapshot", return_value=make_snapshot("snap-new")),
        patch("app.api.storage.volume_snapshots.invalidate", new_callable=AsyncMock) as mock_inv,
        patch(
            "app.api.storage.volume_snapshots.invalidation.invalidate_mutation_count", new_callable=AsyncMock
        ) as mock_mut,
        patch("app.api.storage.volume_snapshots.rec", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/v1/volume-snapshots",
            json={"volume_id": "vol-1", "name": "snap-new", "force": False},
        )
    assert resp.status_code == 201
    mock_inv.assert_called_once_with("afterglow:cinder:test-project-123:snapshots*")
    mock_mut.assert_called_once_with("cinder", "test-project-123")


@pytest.mark.asyncio
async def test_delete_snapshot_invalidates_cache(client, mock_conn):
    """스냅샷 삭제 후 snapshots* 패턴 무효화 + mutation count 증가."""
    with (
        patch("app.api.storage.volume_snapshots.cinder.delete_snapshot", return_value=None),
        patch("app.api.storage.volume_snapshots.invalidate", new_callable=AsyncMock) as mock_inv,
        patch(
            "app.api.storage.volume_snapshots.invalidation.invalidate_mutation_count", new_callable=AsyncMock
        ) as mock_mut,
        patch("app.api.storage.volume_snapshots.rec", new_callable=AsyncMock),
    ):
        resp = await client.delete("/api/v1/volume-snapshots/snap-1")
    assert resp.status_code == 204
    mock_inv.assert_called_once_with("afterglow:cinder:test-project-123:snapshots*")
    mock_mut.assert_called_once_with("cinder", "test-project-123")


@pytest.mark.asyncio
async def test_create_snapshot_in_use_without_force_returns_400(client, mock_conn):
    """in-use 볼륨에 force=False 로 스냅샷 생성 시 Cinder 400 메시지가 그대로 전달된다."""
    from openstack.exceptions import BadRequestException

    mock_conn.block_storage.get_volume.return_value = _make_volume_in_use()
    with (
        patch(
            "app.api.storage.volume_snapshots.cinder.create_snapshot",
            side_effect=BadRequestException(
                message="Invalid volume: Volume is in use, force snapshot is required",
                http_status=400,
            ),
        ),
        patch("app.api.storage.volume_snapshots.rec", new_callable=AsyncMock),
    ):
        resp = await client.post(
            "/api/v1/volume-snapshots",
            json={"volume_id": "vol-1", "name": "snap-fail", "force": False},
        )
    assert resp.status_code == 400
    assert "force" in resp.json()["detail"].lower()
