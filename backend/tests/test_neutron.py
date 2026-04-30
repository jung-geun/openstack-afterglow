"""neutron.ensure_union_egress_sg + ensure_monitoring_ingress_sg 단위 테스트."""

from unittest.mock import MagicMock, patch


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
# A11: ensure_monitoring_ingress_sg 단위 테스트
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
def test_ensure_monitoring_ingress_sg_creates_when_missing(mock_list, mock_create_sg, mock_create_rule):
    """SG 미존재 시 생성 + 2개 ingress rule 등록."""
    from app.services.neutron import ensure_monitoring_ingress_sg

    mock_list.return_value = []
    mock_create_sg.return_value = _make_sg(sg_id="mon-sg-1", name="monitoring")
    conn = MagicMock()

    result = ensure_monitoring_ingress_sg(conn, "proj-1", scrape_cidr="10.0.0.0/8")

    assert result == "monitoring"
    mock_create_sg.assert_called_once()
    assert mock_create_rule.call_count == 2  # node_exporter + dcgm_exporter


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_monitoring_ingress_sg_idempotent(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재 + 모든 rule 존재 시 생성/추가 없음."""
    from app.services.neutron import ensure_monitoring_ingress_sg

    all_rules = [
        _make_ingress_rule("tcp", 9100, 9100, "10.0.0.0/8"),
        _make_ingress_rule("tcp", 9400, 9400, "10.0.0.0/8"),
    ]
    mock_list.return_value = [_make_sg(name="monitoring", rules=all_rules)]
    conn = MagicMock()

    result = ensure_monitoring_ingress_sg(conn, "proj-1", scrape_cidr="10.0.0.0/8")

    assert result == "monitoring"
    mock_create_sg.assert_not_called()
    mock_create_rule.assert_not_called()


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_monitoring_ingress_sg_adds_missing_rule(mock_list, mock_create_sg, mock_create_rule):
    """SG 존재 + 일부 rule 누락 시 누락분만 추가."""
    from app.services.neutron import ensure_monitoring_ingress_sg

    partial_rules = [
        _make_ingress_rule("tcp", 9100, 9100, "10.0.0.0/8"),
        # 9400 누락
    ]
    mock_list.return_value = [_make_sg(name="monitoring", rules=partial_rules)]
    conn = MagicMock()

    ensure_monitoring_ingress_sg(conn, "proj-1", scrape_cidr="10.0.0.0/8")

    mock_create_sg.assert_not_called()
    assert mock_create_rule.call_count == 1


def test_ensure_monitoring_ingress_sg_raises_without_cidr():
    """scrape_cidr 미설정 시 ValueError."""
    from app.services.neutron import ensure_monitoring_ingress_sg

    conn = MagicMock()
    import pytest

    with pytest.raises(ValueError, match="monitoring_scrape_cidr must be set"):
        ensure_monitoring_ingress_sg(conn, "proj-1", scrape_cidr="")


@patch("app.services.neutron.create_security_group_rule")
@patch("app.services.neutron.create_security_group")
@patch("app.services.neutron.list_security_groups")
def test_ensure_monitoring_ingress_sg_custom_name(mock_list, mock_create_sg, mock_create_rule):
    """커스텀 SG 이름 사용."""
    from app.services.neutron import ensure_monitoring_ingress_sg

    mock_list.return_value = []
    mock_create_sg.return_value = _make_sg(name="my-mon-sg")
    conn = MagicMock()

    result = ensure_monitoring_ingress_sg(conn, "proj-1", sg_name="my-mon-sg", scrape_cidr="172.16.0.0/12")

    assert result == "my-mon-sg"
