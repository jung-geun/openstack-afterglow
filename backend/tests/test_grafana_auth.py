"""Grafana 임베드 지원 엔드포인트 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_grafana_dashboards(client):
    """dashboards 엔드포인트가 grafana_url과 대시보드 UID 맵을 반환한다."""
    fake_settings = MagicMock()
    fake_settings.grafana_base_url = "https://grafana.example.com"
    fake_settings.grafana_dashboard_node_uid = "node-uid"
    fake_settings.grafana_dashboard_rabbitmq_uid = "rabbitmq-uid"
    fake_settings.grafana_dashboard_mysqld_uid = "mysqld-uid"
    fake_settings.grafana_dashboard_memcached_uid = "memcached-uid"
    fake_settings.grafana_dashboard_etcd_uid = "etcd-uid"
    fake_settings.grafana_dashboard_haproxy_uid = "haproxy-uid"
    fake_settings.grafana_dashboard_libvirt_uid = "libvirt-uid"
    fake_settings.grafana_dashboard_openstack_uid = "openstack-uid"
    fake_settings.grafana_dashboard_ceph_uid = "ceph-uid"

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.get("/api/grafana/dashboards")

    assert resp.status_code == 200
    data = resp.json()
    assert data["grafana_url"] == "https://grafana.example.com"
    assert data["dashboards"]["node"] == "node-uid"
    assert data["dashboards"]["rabbitmq"] == "rabbitmq-uid"
    assert set(data["dashboards"].keys()) == {"node", "rabbitmq", "mysqld", "memcached", "etcd", "haproxy", "libvirt", "openstack", "ceph"}


@pytest.mark.asyncio
async def test_get_grafana_dashboards_no_url(client):
    """grafana_base_url 미설정 시 빈 문자열 반환 — 프론트엔드가 빈 상태를 판단한다."""
    fake_settings = MagicMock()
    fake_settings.grafana_base_url = ""
    fake_settings.grafana_dashboard_node_uid = "afterglow-node"
    fake_settings.grafana_dashboard_rabbitmq_uid = "afterglow-rabbitmq"
    fake_settings.grafana_dashboard_mysqld_uid = "afterglow-mysqld"
    fake_settings.grafana_dashboard_memcached_uid = "afterglow-memcached"
    fake_settings.grafana_dashboard_etcd_uid = "afterglow-etcd"
    fake_settings.grafana_dashboard_haproxy_uid = "afterglow-haproxy"
    fake_settings.grafana_dashboard_libvirt_uid = "afterglow-libvirt"
    fake_settings.grafana_dashboard_openstack_uid = "afterglow-openstack"
    fake_settings.grafana_dashboard_ceph_uid = "afterglow-ceph"

    with patch("app.api.common.grafana_auth.get_settings", return_value=fake_settings):
        resp = await client.get("/api/grafana/dashboards")

    assert resp.status_code == 200
    assert resp.json()["grafana_url"] == ""
