"""GET /api/grafana/dashboards 엔드포인트 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


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
