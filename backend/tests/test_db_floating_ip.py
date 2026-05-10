"""DB 인스턴스 floating IP 자동 할당 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.api.database.instances import _attach_fip_to_instance_sync


def _mock_instance(ip: str = "192.168.0.166"):
    return {"id": "inst-001", "name": "db1", "status": "ACTIVE", "ip": ip, "ips": [ip]}


def _mock_port(ip: str = "192.168.0.166", port_id: str = "port-1", subnet_id: str = "sub-1"):
    p = MagicMock()
    p.id = port_id
    p.fixed_ips = [{"ip_address": ip, "subnet_id": subnet_id}]
    return p


def _mock_fip(fip_id: str = "fip-1", address: str = "10.0.0.5", port_id: str | None = None):
    f = MagicMock()
    f.id = fip_id
    f.floating_ip_address = address
    f.port_id = port_id
    return f


def test_attach_fip_finds_port_by_ip_match():
    """IP 매칭으로 port 를 찾고 외부 네트워크 → FIP 생성/할당까지 완료."""
    conn = MagicMock()
    conn.network.ports.return_value = iter(
        [_mock_port("10.10.10.10", "port-other"), _mock_port("192.168.0.166", "port-target", "sub-target")]
    )
    conn.network.ips.return_value = iter([])  # 기존 FIP 없음

    with (
        patch("app.services.trove.get_instance", return_value=_mock_instance("192.168.0.166")),
        patch("app.services.neutron.find_external_network_for_subnets", return_value="ext-net-1"),
        patch("app.services.neutron.create_floating_ip", return_value=_mock_fip("fip-new", "10.0.0.5")),
        patch("app.services.neutron.associate_floating_ip") as mock_assoc,
    ):
        result = _attach_fip_to_instance_sync(conn, "inst-001")

    assert result["floating_ip_address"] == "10.0.0.5"
    assert result["port_id"] == "port-target"
    mock_assoc.assert_called_once()
    kwargs = mock_assoc.call_args.kwargs
    assert kwargs.get("port_id") == "port-target"


def test_attach_fip_returns_existing_when_already_attached():
    """이미 port 에 FIP 가 연결되어있으면 새로 만들지 않고 기존 정보를 반환 (멱등)."""
    conn = MagicMock()
    target_port = _mock_port("192.168.0.166", "port-target")
    conn.network.ports.return_value = iter([target_port])
    existing_fip = _mock_fip("fip-existing", "10.0.0.99", "port-target")
    conn.network.ips.return_value = iter([existing_fip])

    with (
        patch("app.services.trove.get_instance", return_value=_mock_instance("192.168.0.166")),
        patch("app.services.neutron.find_external_network_for_subnets", return_value="ext-net-1"),
        patch("app.services.neutron.create_floating_ip") as mock_create,
        patch("app.services.neutron.associate_floating_ip") as mock_assoc,
    ):
        result = _attach_fip_to_instance_sync(conn, "inst-001")

    assert result["floating_ip_address"] == "10.0.0.99"
    assert result["floating_ip_id"] == "fip-existing"
    mock_create.assert_not_called()
    mock_assoc.assert_not_called()


def test_attach_fip_raises_when_no_ip_yet():
    """인스턴스가 아직 IP 미할당(BUILD 중)이면 RuntimeError."""
    conn = MagicMock()
    with patch("app.services.trove.get_instance", return_value=_mock_instance(ip="")):
        with pytest.raises(RuntimeError, match="IP가 아직"):
            _attach_fip_to_instance_sync(conn, "inst-001")


def test_attach_fip_raises_when_no_port():
    """IP 와 매칭되는 port 가 없으면 RuntimeError."""
    conn = MagicMock()
    conn.network.ports.return_value = iter([_mock_port("10.10.10.10", "port-other")])

    with patch("app.services.trove.get_instance", return_value=_mock_instance("192.168.0.166")):
        with pytest.raises(RuntimeError, match="포트를 찾을 수 없습니다"):
            _attach_fip_to_instance_sync(conn, "inst-001")


def test_attach_fip_raises_when_no_external_network():
    """라우터 외부 네트워크가 없으면 RuntimeError."""
    conn = MagicMock()
    conn.network.ports.return_value = iter([_mock_port("192.168.0.166", "port-target", "sub-1")])
    conn.network.ips.return_value = iter([])

    with (
        patch("app.services.trove.get_instance", return_value=_mock_instance("192.168.0.166")),
        patch("app.services.neutron.find_external_network_for_subnets", return_value=None),
    ):
        with pytest.raises(RuntimeError, match="외부 네트워크"):
            _attach_fip_to_instance_sync(conn, "inst-001")
