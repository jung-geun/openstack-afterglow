"""neutron.ensure_union_egress_sg + ensure_monitoring_ingress_sg 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest


def _make_sg(sg_id: str = "sg-1", name: str = "union-egress-default", rules: list | None = None) -> dict:
    return {
        "id": sg_id,
        "name": name,
        "description": "",
        "rules": rules or [],
    }


def _make_rule(protocol: str, port_min: int, port_max: int, direction: str = "egress") -> dict:
    return {
        "id": f"rule-{protocol}-{port_min}",
        "direction": direction,
        "protocol": protocol,
        "port_range_min": port_min,
        "port_range_max": port_max,
        "remote_ip_prefix": "0.0.0.0/0",
        "ethertype": "IPv4",
    }


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_union_egress_sg_creates_when_missing(mock_list, mock_create_sg, mock_create_rule):
    """SG 미존재 시 생성 + 6개 egress rule 등록."""
    from app.services.neutron import ensure_union_egress_sg

    mock_list.return_value = []  # SG 없음
    mock_create_sg.return_value = _make_sg()

    conn = MagicMock()
    result = ensure_union_egress_sg(conn, "proj-1")

    assert result == "union-egress-default"
    mock_create_sg.assert_called_once()
    assert mock_create_rule.call_count == 6  # 6개 rule 등록


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_union_egress_sg_idempotent_when_all_rules_exist(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재 + 모든 rule 존재 시 생성/추가 호출 0."""
    from app.services.neutron import ensure_union_egress_sg

    all_rules = [
        _make_rule("tcp", 2049, 2049),
        _make_rule("udp", 2049, 2049),
        _make_rule("tcp", 6789, 6789),
        _make_rule("tcp", 3300, 3300),
        _make_rule("tcp", 80, 80),
        _make_rule("tcp", 443, 443),
    ]
    mock_list.return_value = [_make_sg(rules=all_rules)]

    conn = MagicMock()
    result = ensure_union_egress_sg(conn, "proj-1")

    assert result == "union-egress-default"
    mock_create_sg.assert_not_called()
    mock_create_rule.assert_not_called()


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_union_egress_sg_adds_missing_rules(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재 + 일부 rule 누락 시 누락분만 추가."""
    from app.services.neutron import ensure_union_egress_sg

    partial_rules = [
        _make_rule("tcp", 2049, 2049),
        _make_rule("udp", 2049, 2049),
        # tcp 6789, 3300, 80, 443 누락
    ]
    mock_list.return_value = [_make_sg(rules=partial_rules)]

    conn = MagicMock()
    ensure_union_egress_sg(conn, "proj-1")

    mock_create_sg.assert_not_called()
    assert mock_create_rule.call_count == 4  # 누락된 4개만 추가


# ---------------------------------------------------------------------------
# A11: _ensure_single_port_ingress_sg / ensure_node_exporter_sg / ensure_dcgm_exporter_sg 단위 테스트
# ---------------------------------------------------------------------------


def _make_ingress_rule(protocol: str, port_min: int, port_max: int, cidr: str = "10.0.0.0/8") -> dict:
    return {
        "id": f"rule-ingress-{protocol}-{port_min}",
        "direction": "ingress",
        "protocol": protocol,
        "port_range_min": port_min,
        "port_range_max": port_max,
        "remote_ip_prefix": cidr,
        "ethertype": "IPv4",
    }


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_single_port_ingress_sg_creates_when_missing(mock_list, mock_create_sg, mock_create_rule):
    """SG 미존재 시 생성 + 1개 ingress rule 등록."""
    from app.services.neutron import _ensure_single_port_ingress_sg

    mock_list.return_value = []
    mock_create_sg.return_value = _make_sg(sg_id="ne-sg-1", name="node_exporter")
    conn = MagicMock()

    result = _ensure_single_port_ingress_sg(
        conn, "proj-1", "node_exporter", port=9100, scrape_cidr="10.0.0.0/8", description="test"
    )

    assert result == "node_exporter"
    mock_create_sg.assert_called_once()
    assert mock_create_rule.call_count == 1
    call_kwargs = mock_create_rule.call_args[1]
    assert call_kwargs["port_range_min"] == 9100
    assert call_kwargs["direction"] == "ingress"
    assert call_kwargs["remote_ip_prefix"] == "10.0.0.0/8"


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_single_port_ingress_sg_idempotent(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재 + rule 존재 시 생성/추가 없음."""
    from app.services.neutron import _ensure_single_port_ingress_sg

    rules = [_make_ingress_rule("tcp", 9100, 9100, "10.0.0.0/8")]
    mock_list.return_value = [_make_sg(name="node_exporter", rules=rules)]
    conn = MagicMock()

    result = _ensure_single_port_ingress_sg(
        conn, "proj-1", "node_exporter", port=9100, scrape_cidr="10.0.0.0/8", description="test"
    )

    assert result == "node_exporter"
    mock_create_sg.assert_not_called()
    mock_create_rule.assert_not_called()


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_single_port_ingress_sg_adds_missing_rule(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재하나 rule 누락 시 rule만 추가."""
    from app.services.neutron import _ensure_single_port_ingress_sg

    mock_list.return_value = [_make_sg(name="node_exporter", rules=[])]
    conn = MagicMock()

    _ensure_single_port_ingress_sg(
        conn, "proj-1", "node_exporter", port=9100, scrape_cidr="10.0.0.0/8", description="test"
    )

    mock_create_sg.assert_not_called()
    assert mock_create_rule.call_count == 1


def test_ensure_single_port_ingress_sg_raises_without_cidr():
    """scrape_cidr 미설정 시 ValueError."""
    import pytest

    from app.services.neutron import _ensure_single_port_ingress_sg

    conn = MagicMock()
    with pytest.raises(ValueError, match="monitoring_scrape_cidr must be set"):
        _ensure_single_port_ingress_sg(conn, "proj-1", "node_exporter", port=9100, scrape_cidr="", description="test")


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_single_port_ingress_sg_custom_name(mock_list, mock_create_sg, mock_create_rule):
    """커스텀 SG 이름 사용."""
    from app.services.neutron import _ensure_single_port_ingress_sg

    mock_list.return_value = []
    mock_create_sg.return_value = _make_sg(name="custom-sg")
    conn = MagicMock()

    result = _ensure_single_port_ingress_sg(
        conn, "proj-1", "custom-sg", port=9400, scrape_cidr="172.16.0.0/12", description="custom"
    )

    assert result == "custom-sg"


@patch("app.services.neutron._ensure_single_port_ingress_sg")
def test_ensure_node_exporter_sg_calls_generic(mock_generic):
    """ensure_node_exporter_sg 가 port=9100, default sg_name='node_exporter' 로 호출."""
    from app.services.neutron import ensure_node_exporter_sg

    mock_generic.return_value = "node_exporter"
    conn = MagicMock()

    result = ensure_node_exporter_sg(conn, "proj-1", scrape_cidr="10.0.0.0/8")

    assert result == "node_exporter"
    _, call_kwargs = mock_generic.call_args[0], mock_generic.call_args[1]
    assert call_kwargs["port"] == 9100
    assert mock_generic.call_args[0][2] == "node_exporter"


@patch("app.services.neutron._ensure_single_port_ingress_sg")
def test_ensure_dcgm_exporter_sg_calls_generic(mock_generic):
    """ensure_dcgm_exporter_sg 가 port=9400, default sg_name='dcgm_exporter' 로 호출."""
    from app.services.neutron import ensure_dcgm_exporter_sg

    mock_generic.return_value = "dcgm_exporter"
    conn = MagicMock()

    result = ensure_dcgm_exporter_sg(conn, "proj-1", scrape_cidr="10.0.0.0/8")

    assert result == "dcgm_exporter"
    _, call_kwargs = mock_generic.call_args[0], mock_generic.call_args[1]
    assert call_kwargs["port"] == 9400
    assert mock_generic.call_args[0][2] == "dcgm_exporter"


def test_strict_network_quota_requires_detailed_floatingip_usage():
    from app.services.neutron import get_network_quota

    conn = MagicMock()
    quota = MagicMock()
    quota.to_dict.return_value = {"floatingip": {"limit": 3}}
    conn.network.get_quota.return_value = quota

    with pytest.raises(ValueError):
        get_network_quota(conn, "project-a", strict=True)


def test_strict_network_quota_does_not_use_limit_only_fallback():
    from app.services.neutron import get_network_quota

    conn = MagicMock()
    conn.network.get_quota.side_effect = RuntimeError("details unavailable")

    with pytest.raises(RuntimeError):
        get_network_quota(conn, "project-a", strict=True)
    conn.network.get_quota.assert_called_once_with("project-a", details=True)


def test_strict_network_quota_preserves_openstacksdk_original_floatingip_key():
    from openstack.network.v2.quota import QuotaDetails

    from app.services.neutron import get_network_quota

    conn = MagicMock()
    conn.network.get_quota.return_value = QuotaDetails.new(floatingip={"limit": 4, "used": 1})

    result = get_network_quota(conn, "project-a", strict=True)

    assert result["floatingip"] == {"limit": 4, "in_use": 1}
    conn.network.get_quota.assert_called_once_with("project-a", details=True)


def test_network_quota_preserves_openstacksdk_original_keys_outside_strict_mode():
    from openstack.network.v2.quota import QuotaDetails

    from app.services.neutron import get_network_quota

    conn = MagicMock()
    conn.network.get_quota.return_value = QuotaDetails.new(
        floatingip={"limit": 5, "used": 2},
        security_group={"limit": 3, "used": 1},
    )
    conn.network.ips.return_value = []
    conn.network.ports.return_value = []

    result = get_network_quota(conn, "project-a")

    assert result["floatingip"] == {"limit": 5, "in_use": 2}
    assert result["security_group"] == {"limit": 3, "in_use": 1}
