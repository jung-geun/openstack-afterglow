"""GET /api/grafana/dashboards 엔드포인트 단위 테스트."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

DASHBOARD_DIR = Path(__file__).parents[2] / "monitoring" / "grafana" / "provisioning" / "dashboards"


def _make_settings(
    grafana_base_url: str = "https://grafana.example.com",
    node_uid: str = "afterglow-node",
    rabbitmq_uid: str = "afterglow-rabbitmq",
    mysqld_uid: str = "afterglow-mysqld",
    memcached_uid: str = "afterglow-memcached",
    etcd_uid: str = "afterglow-etcd",
) -> MagicMock:
    s = MagicMock()
    s.grafana_base_url = grafana_base_url
    s.grafana_dashboard_node_uid = node_uid
    s.grafana_dashboard_rabbitmq_uid = rabbitmq_uid
    s.grafana_dashboard_mysqld_uid = mysqld_uid
    s.grafana_dashboard_memcached_uid = memcached_uid
    s.grafana_dashboard_etcd_uid = etcd_uid
    return s


@pytest.mark.asyncio
async def test_get_dashboards_returns_all_uids(client):
    """정상 설정 시 5개 UID + grafana_url 반환."""
    fake_settings = _make_settings()

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.get("/api/grafana/dashboards")

    assert resp.status_code == 200
    data = resp.json()
    assert data["grafana_url"] == "https://grafana.example.com"
    dashboards = data["dashboards"]
    assert dashboards["node"] == "afterglow-node"
    assert dashboards["rabbitmq"] == "afterglow-rabbitmq"
    assert dashboards["mysqld"] == "afterglow-mysqld"
    assert dashboards["memcached"] == "afterglow-memcached"
    assert dashboards["etcd"] == "afterglow-etcd"


@pytest.mark.asyncio
async def test_get_dashboards_grafana_url_empty(client):
    """grafana_base_url 미설정 시 grafana_url이 빈 문자열로 반환된다 (항상 200)."""
    fake_settings = _make_settings(grafana_base_url="")

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.get("/api/grafana/dashboards")

    assert resp.status_code == 200
    data = resp.json()
    assert data["grafana_url"] == ""
    assert "dashboards" in data


@pytest.mark.asyncio
async def test_get_dashboards_requires_auth(non_admin_client):
    """non-admin 사용자도 dashboards 목록 조회 가능 (인증만 필요)."""
    fake_settings = _make_settings()

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await non_admin_client.get("/api/grafana/dashboards")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_dashboards_custom_uids(client):
    """커스텀 UID 설정이 그대로 반영된다."""
    fake_settings = _make_settings(
        node_uid="custom-node-dashboard",
        rabbitmq_uid="custom-rabbit",
    )

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.get("/api/grafana/dashboards")

    data = resp.json()
    assert data["dashboards"]["node"] == "custom-node-dashboard"
    assert data["dashboards"]["rabbitmq"] == "custom-rabbit"


def test_ceph_dashboard_pool_storage_panel():
    """ceph.json 풀별 저장 용량 패널(id=13)이 올바른 format/transformation을 사용한다."""
    ceph_json = DASHBOARD_DIR / "ceph.json"
    dashboard = json.loads(ceph_json.read_text())

    panel = next(p for p in dashboard["panels"] if p.get("id") == 13)
    target = panel["targets"][0]

    assert target.get("format") == "table", "instant table 쿼리에 format: table 필요"
    assert target.get("instant") is True
    assert "ceph_pool_stored" in target["expr"]
    assert "ceph_pool_metadata" in target["expr"]

    transform_ids = [t["id"] for t in panel.get("transformations", [])]
    assert "reduce" not in transform_ids, "reduce transformation은 table format에서 컬럼명 불일치를 유발함"
    assert "organize" in transform_ids

    organize = next(t for t in panel["transformations"] if t["id"] == "organize")
    rename = organize["options"]["renameByName"]
    assert rename.get("name") == "Pool 이름"
    assert rename.get("Value") == "저장 용량"


def _flatten_panels(dashboard: dict) -> list:
    """row 내부 panels 배열까지 포함해 모든 패널을 평탄화."""
    result = []
    for p in dashboard.get("panels", []):
        if p.get("type") == "row":
            result.extend(p.get("panels", []))
        else:
            result.append(p)
    return result


def test_openstack_dashboard_service_status_panels():
    """openstack.json에 서비스 up/down stat 7개 + 에이전트 활성 비율 stat 3개가 존재한다."""
    dashboard = json.loads((DASHBOARD_DIR / "openstack.json").read_text())
    panels = _flatten_panels(dashboard)

    up_exprs = [
        p["targets"][0]["expr"]
        for p in panels
        if p.get("type") == "stat"
        and p.get("targets")
        and "_up" in p["targets"][0].get("expr", "")
    ]
    for svc in ["nova", "neutron", "cinder", "glance", "identity", "placement", "loadbalancer"]:
        assert any(f"openstack_{svc}_up" in e for e in up_exprs), f"{svc}_up 패널 없음"

    ratio_exprs = [
        p["targets"][0]["expr"]
        for p in panels
        if p.get("type") == "stat" and p.get("targets")
    ]
    for svc in ["nova", "neutron", "cinder"]:
        assert any(
            f"sum(openstack_{svc}_agent_state)" in e and "count(" in e
            for e in ratio_exprs
        ), f"{svc} 에이전트 활성 비율 패널 없음"
