"""neutron.create_port 단위 테스트."""

from unittest.mock import MagicMock


def _make_conn(port_id="port-abc", fixed_ip="10.0.0.5"):
    port = MagicMock()
    port.id = port_id
    port.fixed_ips = [{"ip_address": fixed_ip}]
    conn = MagicMock()
    conn.network.create_port.return_value = port
    return conn


def test_create_port_returns_id_and_ip():
    from app.services.neutron import create_port

    conn = _make_conn("port-123", "10.0.1.10")
    result = create_port(conn, "net-id", "test-port")
    assert result["id"] == "port-123"
    assert result["fixed_ip"] == "10.0.1.10"


def test_create_port_passes_network_id_and_name():
    from app.services.neutron import create_port

    conn = _make_conn()
    create_port(conn, "my-network", "my-port")
    conn.network.create_port.assert_called_once_with(network_id="my-network", name="my-port")


def test_create_port_passes_security_groups():
    from app.services.neutron import create_port

    conn = _make_conn()
    create_port(conn, "net", "p", security_group_ids=["sg-1", "sg-2"])
    call_kwargs = conn.network.create_port.call_args[1]
    # Neutron 포트 API는 UUID 문자열 리스트만 허용 — dict 형식은 400 거부 (실환경 회귀)
    assert call_kwargs["security_groups"] == ["sg-1", "sg-2"]


def test_create_port_no_security_groups_omits_field():
    from app.services.neutron import create_port

    conn = _make_conn()
    create_port(conn, "net", "p")
    call_kwargs = conn.network.create_port.call_args[1]
    assert "security_groups" not in call_kwargs


def test_create_port_empty_fixed_ips():
    from app.services.neutron import create_port

    port = MagicMock()
    port.id = "port-xyz"
    port.fixed_ips = []
    conn = MagicMock()
    conn.network.create_port.return_value = port

    result = create_port(conn, "net", "p")
    assert result["fixed_ip"] == ""
