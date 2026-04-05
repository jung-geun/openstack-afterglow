"""네트워크 및 Floating IP API 테스트."""
import pytest
from unittest.mock import patch
from app.models.storage import FloatingIpInfo


def make_fip(project_id: str = "test-project-123") -> FloatingIpInfo:
    return FloatingIpInfo(
        id="fip-1", floating_ip_address="1.2.3.4",
        fixed_ip_address=None, status="DOWN",
        port_id=None, floating_network_id="net-ext",
        project_id=project_id,
    )


@pytest.mark.asyncio
async def test_list_floating_ips_filters_by_project(client, mock_conn):
    """Floating IP 목록이 현재 프로젝트로 필터링됨을 확인 (Task 2 버그 수정)."""
    captured_project_id = None

    def mock_list_fips(conn, project_id=None):
        nonlocal captured_project_id
        captured_project_id = project_id
        return [make_fip(project_id or "")]

    with patch("app.api.networks.neutron.list_floating_ips", side_effect=mock_list_fips):
        resp = await client.get("/api/networks/floating-ips")

    assert resp.status_code == 200
    # project_id가 전달되었어야 함
    assert captured_project_id == "test-project-123"
