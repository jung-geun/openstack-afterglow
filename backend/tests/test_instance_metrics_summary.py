"""인스턴스 메트릭 요약 + 리사이즈 권장 엔드포인트 테스트."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.compute import FlavorInfo

_PROJECT_ID = "test-project-123"

_FAKE_INSTANCE = MagicMock(
    id="inst-1",
    name="vm-1",
    project_id=_PROJECT_ID,
    flavor_name="m1.large",
    flavor_id="flavor-large",
)

_OTHER_INSTANCE = MagicMock(
    id="inst-other",
    name="vm-other",
    project_id="other-project",
    flavor_name="m1.large",
    flavor_id="flavor-large",
)

_GPU_INSTANCE = MagicMock(
    id="inst-gpu",
    name="vm-gpu",
    project_id=_PROJECT_ID,
    flavor_name="gpu.small",
    flavor_id="flavor-gpu",
)

# 테스트용 플레이버 목록
_LARGE_FLAVOR = FlavorInfo(id="flavor-large", name="m1.large", vcpus=8, ram=16384, disk=50)
_SMALL_FLAVOR = FlavorInfo(id="flavor-small", name="m1.small", vcpus=2, ram=4096, disk=50)
_TINY_DISK_FLAVOR = FlavorInfo(id="flavor-tiny", name="m1.tiny", vcpus=1, ram=1024, disk=20)
_GPU_FLAVOR = FlavorInfo(id="flavor-gpu", name="gpu.small", vcpus=4, ram=8192, disk=50)

_DEFAULT_FLAVORS = [_LARGE_FLAVOR, _SMALL_FLAVOR, _TINY_DISK_FLAVOR, _GPU_FLAVOR]


def _instant(value: float, instance_id: str = "inst-1"):
    """query_instant_multi 반환값 형식."""
    return [({"instance_id": instance_id}, value)]


# ---------------------------------------------------------------------------
# metrics-summary 기본 동작
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summary_returns_stats(client):
    """통계(min/avg/max)가 올바르게 반환되는지 확인."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(5.0)),
        ),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary?range=7d")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prometheus_available"] is True
    assert "cpu" in body["stats"]
    assert body["stats"]["cpu"]["avg"] == 5.0
    assert body["stats"]["memory"]["avg"] == 5.0


@pytest.mark.anyio
async def test_summary_cpu_low_triggers_recommendation(client):
    """CPU 평균 < 10% → underutilized=True, reason에 cpu_avg<10 포함."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(5.0)),
        ),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary?range=7d")
    body = resp.json()
    rec = body["recommendation"]
    assert rec is not None
    assert rec["underutilized"] is True
    assert "cpu_avg<10" in rec["reason"]


@pytest.mark.anyio
async def test_summary_mem_low_triggers_recommendation(client):
    """메모리 평균 < 20%, CPU 정상(≥10%) → underutilized=True, reason에 mem_avg<20 포함."""
    # cpu_avg=15 (정상), mem_avg=12 (낮음)
    # query_instant_multi 호출 순서: 메트릭 4개 × avg/min/max 3종 = 12회
    # 모두 같은 측정값이지만 cpu=15, mem=12로 분기 필요 — return_value 로 통일 후
    # 별도 패치로 cpu 관련 결과만 15.0 반환
    call_counter = {"n": 0}

    async def _side(promql: str):
        call_counter["n"] += 1
        # cpu 식에는 "node_cpu" 또는 "libvirt_domain_info_cpu" 포함
        if "cpu" in promql and "memory" not in promql:
            return _instant(15.0)
        return _instant(12.0)

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch("app.api.compute.instance_metrics.query_instant_multi", side_effect=_side),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary?range=7d")
    body = resp.json()
    rec = body["recommendation"]
    assert rec is not None
    assert rec["underutilized"] is True
    assert "mem_avg<20" in rec["reason"]


@pytest.mark.anyio
async def test_summary_no_recommendation_when_both_normal(client):
    """CPU ≥ 10%, RAM ≥ 20% → underutilized=False."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(50.0)),  # 50% — 높음
        ),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary?range=7d")
    body = resp.json()
    rec = body["recommendation"]
    assert rec is not None
    assert rec["underutilized"] is False


# ---------------------------------------------------------------------------
# 추천 플레이버 알고리즘
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summary_suggested_flavor_excludes_disk_shrink(client):
    """추천 플레이버는 현재 플레이버보다 disk가 작으면 안 됨."""
    # _TINY_DISK_FLAVOR (disk=20) 는 cur_disk=50 미만 → 후보 제외
    # _SMALL_FLAVOR (disk=50, vcpus=2, ram=4096) 는 후보
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(5.0)),
        ),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary?range=7d")
    body = resp.json()
    rec = body["recommendation"]
    assert rec["underutilized"] is True
    suggested = rec["suggested_flavor"]
    assert suggested is not None
    assert suggested["disk"] >= 50  # 현재 disk 이상


@pytest.mark.anyio
async def test_summary_no_suggested_when_no_candidate(client):
    """더 작은 후보가 없으면 suggested_flavor=null."""
    # 현재 인스턴스가 이미 가장 작은 플레이버 사용
    smallest_instance = MagicMock(
        id="inst-small",
        name="vm-small",
        project_id=_PROJECT_ID,
        flavor_name="m1.small",
        flavor_id="flavor-small",
    )
    # m1.small보다 더 작고 disk≥50인 플레이버 없음
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=smallest_instance),
        patch(
            "app.api.compute.instance_metrics.nova.list_flavors",
            return_value=[_SMALL_FLAVOR, _LARGE_FLAVOR, _GPU_FLAVOR],
        ),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(5.0, "inst-small")),
        ),
    ):
        resp = await client.get("/api/instances/inst-small/metrics-summary?range=7d")
    body = resp.json()
    rec = body["recommendation"]
    assert rec["underutilized"] is True
    assert rec["suggested_flavor"] is None


@pytest.mark.anyio
async def test_summary_gpu_instance_no_recommendation(client):
    """GPU 인스턴스는 권장 제외 (recommendation=null)."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_GPU_INSTANCE),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(1.0, "inst-gpu")),
        ),
    ):
        resp = await client.get("/api/instances/inst-gpu/metrics-summary?range=7d")
    body = resp.json()
    assert body["recommendation"] is None


# ---------------------------------------------------------------------------
# 권한 / 404
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summary_unauthorized_other_project(client):
    """다른 프로젝트 인스턴스 → 403."""
    with patch("app.api.compute.instance_metrics.nova.get_server", return_value=_OTHER_INSTANCE):
        resp = await client.get("/api/instances/inst-other/metrics-summary")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_summary_admin_can_access_any(admin_client):
    """관리자는 다른 프로젝트 인스턴스도 조회 가능."""
    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_OTHER_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=_instant(50.0, "inst-other")),
        ),
    ):
        resp = await admin_client.get("/api/instances/inst-other/metrics-summary")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_summary_instance_not_found(client):
    """인스턴스 없음 → 404."""
    with patch("app.api.compute.instance_metrics.nova.get_server", side_effect=Exception("not found")):
        resp = await client.get("/api/instances/bad-id/metrics-summary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Prometheus 불가 폴백
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summary_prom_unavailable_returns_200(client):
    """Prometheus 연결 불가 시 200 + prometheus_available=false."""
    from app.services.prom_query import PromUnavailable

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(side_effect=PromUnavailable("down")),
        ),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prometheus_available"] is False
    assert body["stats"] == {}
    assert body["recommendation"] is None


# ---------------------------------------------------------------------------
# libvirt 폴백
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summary_libvirt_fallback(client):
    """node_exporter 결과가 없으면 libvirt expr로 폴백."""
    call_order = []

    async def _side(promql: str):
        call_order.append(promql)
        # node_exporter 식(node_cpu_seconds_total 등)은 빈 결과 반환
        if "node_cpu" in promql or "node_memory" in promql or "node_disk" in promql:
            return []
        # libvirt 식은 값 반환
        return _instant(8.0)

    with (
        patch("app.api.compute.instance_metrics.nova.get_server", return_value=_FAKE_INSTANCE),
        patch("app.api.compute.instance_metrics.nova.list_flavors", return_value=_DEFAULT_FLAVORS),
        patch("app.api.compute.instance_metrics.query_instant_multi", side_effect=_side),
    ):
        resp = await client.get("/api/instances/inst-1/metrics-summary")
    assert resp.status_code == 200
    # libvirt 폴백으로 값이 채워졌으면 libvirt 식이 호출됐어야 함
    libvirt_calls = [p for p in call_order if "libvirt" in p]
    assert len(libvirt_calls) > 0


# ---------------------------------------------------------------------------
# metrics-summary-batch
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_batch_returns_per_instance_data(client):
    """batch: project_id로 필터된 인스턴스 별 cpu_avg/mem_avg/underutilized 반환."""
    cpu_results = [({"instance_id": "inst-1"}, 5.0), ({"instance_id": "inst-2"}, 50.0)]
    mem_results = [({"instance_id": "inst-1"}, 15.0), ({"instance_id": "inst-2"}, 60.0)]

    call_count = {"n": 0}

    async def _side(promql: str):
        call_count["n"] += 1
        # 첫 호출(cpu_node), 세 번째 호출(cpu_lv) 는 cpu 관련
        if "cpu" in promql and "memory" not in promql and "libvirt" not in promql:
            return cpu_results
        if "memory" in promql and "libvirt" not in promql:
            return mem_results
        return []  # libvirt 폴백 — 이미 node 결과 있으므로 merge 안 됨

    with patch("app.api.compute.instance_metrics.query_instant_multi", side_effect=_side):
        resp = await client.get("/api/instances/metrics-summary-batch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prometheus_available"] is True
    instances = body["instances"]
    assert "inst-1" in instances
    assert instances["inst-1"]["underutilized"] is True  # cpu<10 AND mem<20
    assert instances["inst-2"]["underutilized"] is False  # cpu=50, mem=60 — 정상


@pytest.mark.anyio
async def test_batch_invalid_project_id_returns_empty(client):
    """비정상 project_id 형식(주입 위험) 시 instances={} 반환, Prometheus 조회 안 함."""
    from app.api.deps import get_token_info
    from app.main import app

    async def _bad_token():
        return {
            "token": "test-token",
            "project_id": "../../etc/passwd",  # 주입 시도
            "user_id": "u1",
            "is_system_admin": False,
        }

    app.dependency_overrides[get_token_info] = _bad_token
    try:
        with patch(
            "app.api.compute.instance_metrics.query_instant_multi",
            new=AsyncMock(return_value=[]),
        ) as mock_q:
            resp = await client.get("/api/instances/metrics-summary-batch")
        assert resp.status_code == 200
        assert resp.json()["instances"] == {}
        mock_q.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_token_info, None)


@pytest.mark.anyio
async def test_batch_prom_unavailable_returns_200(client):
    """batch: Prometheus 연결 불가 시 200 + prometheus_available=false."""
    from app.services.prom_query import PromUnavailable

    with patch(
        "app.api.compute.instance_metrics.query_instant_multi",
        new=AsyncMock(side_effect=PromUnavailable("down")),
    ):
        resp = await client.get("/api/instances/metrics-summary-batch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["prometheus_available"] is False
    assert body["instances"] == {}
