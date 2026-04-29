"""neutron.ensure_union_egress_sg 단위 테스트."""

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
