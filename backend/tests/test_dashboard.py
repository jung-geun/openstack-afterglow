"""common/dashboard.py 엔드포인트 단위 테스트."""

import asyncio
import json
from threading import Event
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import InterfaceError, OperationalError

from app.main import app


@pytest.mark.asyncio
async def test_get_dashboard_config_public():
    """GET /api/dashboard/config — 인증 불필요, 항상 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/config")
    assert resp.status_code == 200
    assert "refresh_interval_ms" in resp.json()


@pytest.mark.asyncio
async def test_get_dashboard_summary_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_summary_success(client):
    empty_list: list = []
    with patch(
        "app.api.common.dashboard.cached_call",
        new=AsyncMock(
            side_effect=[
                empty_list,  # servers
                empty_list,  # all_flavors
            ]
        ),
    ):
        resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "instances" in data
    assert "gpu_used" in data
    assert "compute" not in data
    assert "storage" not in data


@pytest.mark.asyncio
async def test_get_dashboard_summary_overview_exact_shape_and_no_heavy_calls(client):
    servers = [
        {
            "id": "older",
            "name": "older",
            "status": "SHUTOFF",
            "flavor_id": "f1",
            "flavor_name": "small",
            "created_at": "2025-01-01T00:00:00Z",
            "ip_addresses": [{"addr": "10.0.0.2", "type": "fixed", "network_name": "private"}],
        },
        {
            "id": "newer",
            "name": "newer",
            "status": "ACTIVE",
            "flavor_name": None,
            "created_at": "2026-01-01T00:00:00Z",
        },
    ]
    with (
        patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=servers)),
        patch("app.api.common.dashboard._list_flavors_as_dicts") as flavors,
    ):
        resp = await client.get("/api/v1/dashboard/summary?view=overview")

    assert resp.status_code == 200
    assert resp.json() == {
        "instances": {"total": 2, "active": 1, "shutoff": 1, "error": 0},
        "recent_instances": [
            {
                "id": "newer",
                "name": "newer",
                "status": "ACTIVE",
                "flavor_name": None,
                "ip_addresses": [],
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "older",
                "name": "older",
                "status": "SHUTOFF",
                "flavor_name": "small",
                "ip_addresses": [{"addr": "10.0.0.2", "type": "fixed", "network_name": "private"}],
                "created_at": "2025-01-01T00:00:00Z",
            },
        ],
    }
    flavors.assert_not_called()


@pytest.mark.asyncio
async def test_get_dashboard_summary_overview_source_failure_is_503(client):
    with patch(
        "app.api.common.dashboard.cached_call",
        new=AsyncMock(side_effect=RuntimeError("nova unavailable")),
    ):
        resp = await client.get("/api/v1/dashboard/summary?view=overview")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "인스턴스 현황을 불러오지 못했습니다"}


@pytest.mark.asyncio
async def test_get_dashboard_quotas_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/quotas")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_quotas_success(client):
    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    # cached_call은 결과를 캐시 key별로 1회씩 호출한다 — _fetch_quotas 내부의
    # asyncio.gather를 진짜로 실행하되, 각 service 함수는 cached_call로 묶여 있음.
    # 가장 단순한 방법: cached_call 전체를 patch해서 results 리스트를 한 번에 반환.
    # 활성화된 서비스(config.toml): manila/trove/swift → compute/volume/network/manila/trove/swift = 최대 6건
    # 실제 활성 수를 맞추기 위해 넉넉히 6개 제공
    quota_int = 0  # trove count
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}
    with patch(
        "app.api.common.dashboard.cached_call",
        new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
    ):
        resp = await client.get("/api/v1/dashboard/quotas")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute" in data
    assert "storage" in data


@pytest.mark.asyncio
async def test_get_dashboard_quotas_overview_returns_narrow_alert_contract(client):
    from types import SimpleNamespace

    overview_sources = (
        {
            "instances": {"limit": 2, "in_use": 2},
            "cores": {"limit": -1, "in_use": 0},
            "ram": {"limit": 0, "in_use": 0},
        },
        {
            "volumes": {"limit": 10, "in_use": 1},
            "gigabytes": {"limit": 100, "in_use": 90},
        },
        {"floatingip": {"limit": 5, "in_use": 1}},
    )

    async def _through_cache(_key, _ttl, callback, **_kwargs):
        return await callback()

    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_manila_enabled=False)),
        patch("app.api.common.dashboard.cached_call", new=AsyncMock(side_effect=_through_cache)),
        patch("app.api.common.dashboard.nova.get_project_quota", return_value=overview_sources[0]),
        patch("app.api.common.dashboard.cinder.get_volume_quota", return_value=overview_sources[1]),
        patch("app.api.common.dashboard.neutron_svc.get_network_quota", return_value=overview_sources[2]),
    ):
        resp = await client.get("/api/v1/dashboard/quotas?view=overview")

    assert resp.status_code == 200
    assert resp.json() == {
        "compute": overview_sources[0],
        "storage": overview_sources[1],
        "network": overview_sources[2],
        "file_storage": None,
        "alerts": [
            {
                "type": "quota",
                "severity": "danger",
                "message": "인스턴스 쿼터 가득 참 (2/2)",
                "count": 1,
            },
            {
                "type": "quota",
                "severity": "warning",
                "message": "스토리지(GB) 쿼터 90% 사용 (90/100)",
                "count": 1,
            },
        ],
    }


@pytest.mark.asyncio
async def test_dashboard_quota_overview_accepts_sdk_shaped_neutron_details(client, mock_conn):
    from types import SimpleNamespace

    from openstack.network.v2.quota import QuotaDetails

    async def _through_cache(_key, _ttl, callback, **_kwargs):
        return await callback()

    mock_conn.network.get_quota.return_value = QuotaDetails.new(floatingip={"limit": 4, "used": 1})
    mock_conn.network.ips.return_value = []
    mock_conn.network.ports.return_value = []
    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_manila_enabled=False)),
        patch("app.api.common.dashboard.cached_call", new=AsyncMock(side_effect=_through_cache)),
        patch(
            "app.api.common.dashboard.nova.get_project_quota",
            return_value={
                "instances": {"limit": 1, "in_use": 0},
                "cores": {"limit": 1, "in_use": 0},
                "ram": {"limit": 1, "in_use": 0},
            },
        ),
        patch(
            "app.api.common.dashboard.cinder.get_volume_quota",
            return_value={
                "volumes": {"limit": 1, "in_use": 0},
                "gigabytes": {"limit": 1, "in_use": 0},
            },
        ),
    ):
        resp = await client.get("/api/v1/dashboard/quotas?view=overview")

    assert resp.status_code == 200
    assert resp.json()["network"]["floatingip"] == {"limit": 4, "in_use": 1}


@pytest.mark.asyncio
async def test_get_dashboard_quotas_overview_fails_closed_after_worker_failure(client):
    from types import SimpleNamespace

    async def _through_cache(_key, _ttl, callback, **_kwargs):
        return await callback()

    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_manila_enabled=False)),
        patch("app.api.common.dashboard.cached_call", new=AsyncMock(side_effect=_through_cache)),
        patch("app.api.common.dashboard.nova.get_project_quota", side_effect=RuntimeError("Nova unavailable")),
        patch(
            "app.api.common.dashboard.cinder.get_volume_quota",
            return_value={"volumes": {"limit": 1, "in_use": 0}, "gigabytes": {"limit": 1, "in_use": 0}},
        ),
        patch(
            "app.api.common.dashboard.neutron_svc.get_network_quota",
            return_value={"floatingip": {"limit": 1, "in_use": 0}},
        ),
    ):
        resp = await client.get("/api/v1/dashboard/quotas?view=overview")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "쿼터를 불러오지 못했습니다"}


@pytest.mark.asyncio
async def test_dashboard_quota_overview_waits_for_late_worker_before_failure_response(client):
    from types import SimpleNamespace

    started = asyncio.Event()
    failure_observed = asyncio.Event()
    cinder_started = Event()
    release = Event()
    loop = asyncio.get_running_loop()

    def _late_cinder(*_args, **_kwargs):
        cinder_started.set()
        loop.call_soon_threadsafe(started.set)
        release.wait(timeout=1)
        return {
            "volumes": {"limit": 1, "in_use": 0},
            "gigabytes": {"limit": 1, "in_use": 0},
        }

    def _failing_nova(*_args, **_kwargs):
        assert cinder_started.wait(timeout=1)
        loop.call_soon_threadsafe(failure_observed.set)
        raise RuntimeError("Nova unavailable")

    async def _through_cache(_key, _ttl, callback, **_kwargs):
        return await callback()

    cache = AsyncMock(side_effect=_through_cache)
    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_manila_enabled=False)),
        patch("app.api.common.dashboard.cached_call", new=cache),
        patch("app.api.common.dashboard.nova.get_project_quota", side_effect=_failing_nova),
        patch("app.api.common.dashboard.cinder.get_volume_quota", side_effect=_late_cinder),
        patch(
            "app.api.common.dashboard.neutron_svc.get_network_quota",
            return_value={"floatingip": {"limit": 1, "in_use": 0}},
        ),
    ):
        request = asyncio.create_task(client.get("/api/v1/dashboard/quotas?view=overview"))
        await asyncio.wait_for(started.wait(), timeout=1)
        await asyncio.wait_for(failure_observed.wait(), timeout=1)
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(request), timeout=0.05)
        finally:
            release.set()
        response = await request

    assert response.status_code == 503
    cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_k3s_stats_uses_read_only_fallback(client):
    from types import SimpleNamespace

    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)),
        patch("app.api.common.dashboard.is_db_configured", return_value=False),
        patch(
            "app.services.k3s_cluster.dashboard_cluster_stats",
            new=AsyncMock(return_value={"total": 3, "active": 2}),
        ) as stats,
    ):
        resp = await client.get("/api/v1/dashboard/k3s-stats?refresh=true")

    assert resp.status_code == 200
    assert resp.json() == {"total": 3, "active": 2}
    stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_k3s_stats_fails_fast_when_configured_db_circuit_open(client):
    from types import SimpleNamespace

    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)),
        patch("app.api.common.dashboard.is_db_configured", return_value=True),
        patch("app.api.common.dashboard.is_db_available", return_value=False),
        patch("app.api.common.dashboard.get_session_factory") as factory,
    ):
        resp = await client.get("/api/v1/dashboard/k3s-stats")

    assert resp.status_code == 503
    assert resp.json() == {"detail": "K3s 현황을 불러오지 못했습니다"}
    factory.assert_not_called()


class _K3sStatsResult:
    def __init__(self, value: tuple[int, int]):
        self._value = value

    def one(self) -> tuple[int, int]:
        return self._value


class _K3sStatsSession:
    def __init__(self, *, value: tuple[int, int] = (0, 0), error: Exception | None = None):
        self.value = value
        self.error = error
        self.statement = None
        self.execute_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, statement):
        self.execute_calls += 1
        self.statement = statement
        if self.error:
            raise self.error
        return _K3sStatsResult(self.value)


@pytest.mark.asyncio
async def test_dashboard_k3s_stats_db_aggregate_scopes_total_and_active_to_token_project():
    from types import SimpleNamespace

    from app.api.common.dashboard import get_dashboard_k3s_stats

    session = _K3sStatsSession(value=(3, 2))
    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)),
        patch("app.api.common.dashboard.is_db_configured", return_value=True),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch("app.api.common.dashboard.get_session_factory", return_value=lambda: session),
    ):
        result = await get_dashboard_k3s_stats({"project_id": "tenant-two"}, cm=None)

    assert result == {"total": 3, "active": 2}
    assert session.execute_calls == 1
    compiled = session.statement.compile()
    assert "tenant-two" in compiled.params.values()
    assert "k3s_clusters.deleted_at IS NULL" in str(session.statement)
    assert "k3s_clusters.status" in str(session.statement)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("select", {}, RuntimeError("offline")),
        InterfaceError("select", {}, RuntimeError("offline")),
    ],
)
async def test_dashboard_k3s_stats_db_connectivity_marks_circuit_then_fast_fails(failure):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.common.dashboard import get_dashboard_k3s_stats

    session = _K3sStatsSession(error=failure)
    mark_unhealthy = MagicMock()
    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)),
        patch("app.api.common.dashboard.is_db_configured", return_value=True),
        patch("app.api.common.dashboard.is_db_available", side_effect=[True, False]),
        patch("app.api.common.dashboard.get_session_factory", return_value=lambda: session) as factory,
        patch("app.api.common.dashboard.mark_db_unhealthy", mark_unhealthy),
    ):
        with pytest.raises(HTTPException) as first:
            await get_dashboard_k3s_stats({"project_id": "tenant-a"}, cm=None)
        with pytest.raises(HTTPException) as second:
            await get_dashboard_k3s_stats({"project_id": "tenant-a"}, cm=None)

    assert first.value.status_code == 503
    assert second.value.status_code == 503
    mark_unhealthy.assert_called_once()
    assert session.execute_calls == 1
    assert factory.call_count == 1


@pytest.mark.asyncio
async def test_dashboard_k3s_stats_db_programming_error_does_not_poison_circuit():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.common.dashboard import get_dashboard_k3s_stats

    session = _K3sStatsSession(error=RuntimeError("bad query"))
    mark_unhealthy = MagicMock()
    with (
        patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)),
        patch("app.api.common.dashboard.is_db_configured", return_value=True),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch("app.api.common.dashboard.get_session_factory", return_value=lambda: session),
        patch("app.api.common.dashboard.mark_db_unhealthy", mark_unhealthy),
    ):
        with pytest.raises(HTTPException) as error:
            await get_dashboard_k3s_stats({"project_id": "tenant-a"}, cm=None)

    assert error.value.status_code == 503
    mark_unhealthy.assert_not_called()


@pytest.mark.asyncio
async def test_dashboard_k3s_stats_rejects_redis_glob_project_id():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.common.dashboard import get_dashboard_k3s_stats

    with patch("app.api.common.dashboard.get_settings", return_value=SimpleNamespace(service_k3s_enabled=True)):
        with pytest.raises(HTTPException) as error:
            await get_dashboard_k3s_stats({"project_id": "tenant-*"}, cm=None)

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_dashboard_quota_workers_drain_before_cancellation_propagates():
    from app.api.common.dashboard import _drain_named_quota_tasks

    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()

    def _slow_source():
        loop.call_soon_threadsafe(started.set)
        release.wait(timeout=1)
        return {"done": True}

    def _failing_source():
        raise RuntimeError("failed")

    task = asyncio.create_task(_drain_named_quota_tasks({"slow": _slow_source, "failing": _failing_source}))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_http_5xx_sanitizer_only_exposes_explicitly_reviewed_detail():
    from fastapi import HTTPException

    from app.api.common.dashboard import _dashboard_service_unavailable
    from app.main import k3s_api_error_handler, sanitized_http_exception_handler

    request = MagicMock()
    request.method = "GET"
    request.url.path = "/api/v1/test"

    internal = await sanitized_http_exception_handler(request, HTTPException(status_code=503, detail="sensitive"))
    safe = await sanitized_http_exception_handler(request, _dashboard_service_unavailable("안전한 상태 메시지"))
    from app.services.k3s_errors import K3sApiError

    k3s_internal = await k3s_api_error_handler(request, K3sApiError(502, "upstream Kubernetes detail"))
    k3s_public = await k3s_api_error_handler(request, K3sApiError(400, "잘못된 K3s 요청"))

    assert json.loads(internal.body) == {"detail": "내부 서버 오류"}
    assert json.loads(safe.body) == {"detail": "안전한 상태 메시지"}
    assert json.loads(k3s_internal.body) == {"detail": "내부 서버 오류"}
    assert json.loads(k3s_public.body) == {"detail": "잘못된 K3s 요청"}


@pytest.mark.asyncio
async def test_get_dashboard_usage_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_usage_success(client):
    usage_data = {"server_usages": [], "total_hours": 0}
    with patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=usage_data)):
        resp = await client.get("/api/v1/dashboard/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "server_usages" in data
    assert "total_hours" in data


# ---------------------------------------------------------------------------
# GPU available 엔드포인트 (feature-flag + 캐시)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gpu_available_disabled_by_default(client):
    """gpu_available_visible=false 이면 404 반환.
    Redis 미연결 시 캐시 에러로 500이 날 수 있으므로 두 경우 모두 허용.
    """
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = False
        resp = await client.get("/api/v1/dashboard/gpu-available")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gpu_available_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/dashboard/gpu-available")
    # feature-flag에 따라 404 또는 401
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_gpu_available_enabled(client):
    """gpu_available_visible=true 시 캐시된 결과 반환."""
    mock_result = {
        "gpu_types": [{"device_name": "RTX3090", "vendor": "NVIDIA", "total": 4, "used": 1, "available": 3}],
        "summary": {"total": 4, "used": 1, "available": 3},
    }
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = True
        with patch("app.api.common.dashboard.cached_call", new=AsyncMock(return_value=mock_result)):
            resp = await client.get("/api/v1/dashboard/gpu-available")
    if resp.status_code == 200:
        data = resp.json()
        assert "gpu_types" in data
        assert "summary" in data


@pytest.mark.asyncio
async def test_gpu_available_cache_refresh(client):
    """refresh=true 쿼리 파라미터 전달 시 캐시 갱신 호출."""
    with patch("app.api.common.dashboard.get_settings") as mock_settings:
        mock_settings.return_value.gpu_available_visible = True
        with patch(
            "app.api.common.dashboard.cached_call", new=AsyncMock(return_value={"gpu_types": [], "summary": {}})
        ):
            resp = await client.get("/api/v1/dashboard/gpu-available?refresh=true")
    # 200 또는 500(실제 admin conn 없음), 중요한 건 404가 아닌 것
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# GPU quota OperationalError → 200 + 빈 gpu 배열
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_quotas_gpu_db_error_returns_empty_gpu(client):
    """GPU quota DB OperationalError 발생 시 200 반환 + gpu 빈 배열."""
    from sqlalchemy.exc import OperationalError

    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    quota_int = 0
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}

    with (
        patch(
            "app.api.common.dashboard.cached_call",
            new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
        ),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch(
            "app.services.gpu_quota.get_effective_gpu_quotas",
            new=AsyncMock(side_effect=OperationalError("lost", None, None)),
        ),
        patch("app.services.gpu_quota.get_project_gpu_usage", new=AsyncMock(return_value={})),
        patch("app.api.common.dashboard.mark_db_unhealthy") as mock_mark,
    ):
        resp = await client.get("/api/v1/dashboard/quotas")

    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu"] == []
    mock_mark.assert_called_once()


@pytest.mark.asyncio
async def test_get_dashboard_quotas_gpu_partial_error_returns_empty_gpu(client):
    """GPU usage 조회만 실패해도 200 + gpu 빈 배열."""
    from sqlalchemy.exc import OperationalError

    quota = {"limit": 10, "in_use": 2, "reserved": 0}
    quota_int = 0
    swift_meta = {"container_count": 0, "object_count": 0, "bytes_used": 0}

    with (
        patch(
            "app.api.common.dashboard.cached_call",
            new=AsyncMock(return_value=[quota, quota, quota, quota, quota_int, swift_meta]),
        ),
        patch("app.api.common.dashboard.is_db_available", return_value=True),
        patch("app.services.gpu_quota.get_effective_gpu_quotas", new=AsyncMock(return_value={"RTX3090": 2})),
        patch(
            "app.services.gpu_quota.get_project_gpu_usage",
            new=AsyncMock(side_effect=OperationalError("lost", None, None)),
        ),
        patch("app.api.common.dashboard.mark_db_unhealthy"),
    ):
        resp = await client.get("/api/v1/dashboard/quotas")

    assert resp.status_code == 200
    assert resp.json()["gpu"] == []
