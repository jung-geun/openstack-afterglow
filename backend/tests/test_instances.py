"""인스턴스 API 단위 테스트."""

from unittest.mock import patch

import pytest

from app.models.compute import InstanceInfo


def make_instance(instance_id: str = "inst-1", name: str = "test-vm", status: str = "ACTIVE") -> InstanceInfo:
    return InstanceInfo(
        id=instance_id,
        name=name,
        status=status,
        image_id="img-1",
        image_name="ubuntu-22.04",
        flavor_id="flavor-1",
        flavor_name="m1.small",
        ip_addresses=[],
        created_at="2024-01-01T00:00:00Z",
        metadata={},
        union_libraries=[],
        union_strategy=None,
        union_share_ids=[],
        union_upper_volume_id=None,
        key_name=None,
        user_id="test-user-123",
    )


# ────── GET 목록 & 상세 ──────


@pytest.mark.asyncio
async def test_list_instances(client, mock_conn):
    with (
        patch("app.api.compute.instances.nova.list_servers", return_value=[make_instance()]),
        patch("app.api.compute.instances.nova.list_flavors", return_value=[]),
        patch("app.api.compute.instances.glance.list_images", return_value=[]),
        patch("app.api.compute.instances.nova.list_volume_attachments", return_value=[]),
        patch("app.api.compute.instances.cinder.get_volume_image_metadata", return_value={}),
    ):
        resp = await client.get("/api/instances")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_instance(client, mock_conn):
    with (
        patch("app.api.compute.instances.nova.get_server", return_value=make_instance()),
        patch("app.api.compute.instances.nova.list_flavors", return_value=[]),
        patch("app.api.compute.instances.glance.list_images", return_value=[]),
    ):
        resp = await client.get("/api/instances/inst-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "inst-1"


# ────── DELETE ──────


@pytest.mark.asyncio
async def test_delete_instance(client, mock_conn):
    inst = make_instance()
    inst.metadata = {}
    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.cinder.delete_volume", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_instance_cleans_nfs_access_rules(client, mock_conn):
    """prebuilt strategy VM 삭제 시 NFS access rule이 revoke되어야 한다."""
    from app.models.compute import IpAddress

    inst = make_instance()
    inst.union_strategy = "prebuilt"
    inst.union_share_ids = ["share-1"]
    inst.ip_addresses = [IpAddress(addr="10.0.0.5", type="fixed")]

    access_rules = [
        {"id": "rule-1", "access_type": "ip", "access_to": "10.0.0.5"},
        {"id": "rule-2", "access_type": "ip", "access_to": "192.168.1.1"},  # 다른 VM의 rule
    ]
    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.manila.list_access_rules", return_value=access_rules) as mock_list,
        patch("app.api.compute.instances.manila.revoke_access_rule") as mock_revoke,
        patch("app.api.compute.instances.neutron.cleanup_instance_fips", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")

    assert resp.status_code == 204
    mock_list.assert_called_once_with(mock_conn, "share-1")
    # IP가 일치하는 rule-1만 revoke
    mock_revoke.assert_called_once_with(mock_conn, "share-1", "rule-1")


@pytest.mark.asyncio
async def test_delete_instance_nfs_cleanup_failure_continues(client, mock_conn):
    """NFS access rule 정리 실패해도 VM 삭제는 계속된다."""
    from app.models.compute import IpAddress

    inst = make_instance()
    inst.union_strategy = "prebuilt"
    inst.union_share_ids = ["share-1"]
    inst.ip_addresses = [IpAddress(addr="10.0.0.5", type="fixed")]

    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.manila.list_access_rules", side_effect=Exception("Manila 오류")),
        patch("app.api.compute.instances.neutron.cleanup_instance_fips", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_instance_dynamic_skips_nfs_rule_cleanup(client, mock_conn):
    """dynamic strategy 삭제 시 NFS access rule 조회를 건너뛴다."""
    inst = make_instance()
    inst.union_strategy = "dynamic"
    inst.union_share_ids = ["share-1"]

    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.manila.delete_file_storage", return_value=None),
        patch("app.api.compute.instances.manila.list_access_rules") as mock_list,
        patch("app.api.compute.instances.neutron.cleanup_instance_fips", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")

    assert resp.status_code == 204
    mock_list.assert_not_called()


# ────── 라이프사이클 액션 ──────


@pytest.mark.asyncio
async def test_start_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.start_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/start")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_stop_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.stop_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/stop")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reboot_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.reboot_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/reboot")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_shelve_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.shelve_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/shelve")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_unshelve_instance(client, mock_conn):
    with patch("app.api.compute.instances.nova.unshelve_server", return_value=None):
        resp = await client.post("/api/instances/inst-1/unshelve")
    assert resp.status_code == 204


# ────── 콘솔/로그 ──────


@pytest.mark.asyncio
async def test_get_console(client, mock_conn):
    with patch("app.api.compute.instances.nova.get_console_url", return_value="https://console.example.com"):
        resp = await client.get("/api/instances/inst-1/console")
    assert resp.status_code == 200
    assert "url" in resp.json()


@pytest.mark.asyncio
async def test_get_console_log(client, mock_conn):
    with patch("app.api.compute.instances.nova.get_console_output", return_value="log output"):
        resp = await client.get("/api/instances/inst-1/log")
    assert resp.status_code == 200
    assert "output" in resp.json()


@pytest.mark.asyncio
async def test_get_console_log_full(client, mock_conn):
    """length=0은 전체 로그 요청 — 422가 아닌 200 반환되어야 한다."""
    with patch("app.api.compute.instances.nova.get_console_output", return_value="full log"):
        resp = await client.get("/api/instances/inst-1/log?length=0")
    assert resp.status_code == 200
    assert resp.json()["output"] == "full log"


@pytest.mark.asyncio
async def test_get_console_log_length_negative(client, mock_conn):
    """음수 length는 거부되어야 한다."""
    resp = await client.get("/api/instances/inst-1/log?length=-1")
    assert resp.status_code == 422


# ────── 볼륨 Attach/Detach ──────


@pytest.mark.asyncio
async def test_attach_volume(client, mock_conn):
    with patch("app.api.compute.instances.nova.attach_volume", return_value={"id": "attach-1", "volumeId": "vol-1"}):
        resp = await client.post("/api/instances/inst-1/volumes", json={"volume_id": "vol-1"})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_detach_volume(client, mock_conn):
    with patch("app.api.compute.instances.nova.detach_volume", return_value=None):
        resp = await client.delete("/api/instances/inst-1/volumes/vol-1")
    assert resp.status_code == 204


# ────── 인터페이스 Attach/Detach ──────


@pytest.mark.asyncio
async def test_attach_interface(client, mock_conn):
    with patch(
        "app.api.compute.instances.nova.attach_interface",
        return_value={"port_id": "port-1", "net_id": "net-1", "ip_address": "10.0.0.2"},
    ):
        resp = await client.post("/api/instances/inst-1/interfaces", json={"net_id": "net-1"})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_detach_interface(client, mock_conn):
    with patch("app.api.compute.instances.nova.detach_interface", return_value=None):
        resp = await client.delete("/api/instances/inst-1/interfaces/port-1")
    assert resp.status_code == 204


# ────── 입력 검증 ──────


@pytest.mark.asyncio
async def test_create_instance_invalid_name(client, mock_conn):
    """인스턴스 이름 regex 검증 — 특수문자 포함 시 422."""
    resp = await client.post(
        "/api/instances",
        json={
            "name": "invalid name!",
            "image_id": "img-1",
            "flavor_id": "flavor-1",
            "network_id": "net-1",
        },
    )
    assert resp.status_code == 422


# ────── Floating IP 해제 — cleanup_instance_fips 범위 검증 ──────


def _make_port(pid: str):
    from unittest.mock import MagicMock

    p = MagicMock()
    p.id = pid
    return p


def _make_fip(fid: str, port_id: str | None):
    from unittest.mock import MagicMock

    f = MagicMock()
    f.id = fid
    f.port_id = port_id
    return f


@pytest.mark.asyncio
async def test_release_floating_ip_only_targets_instance_ports(client, mock_conn):
    """해제 시 해당 인스턴스 포트에 연결된 FIP만 update/delete 한다."""
    mock_conn.network.ports.return_value = [_make_port("p1"), _make_port("p2")]
    mock_conn.network.ips.return_value = [
        _make_fip("fip-1", "p1"),  # 대상 인스턴스 포트
        _make_fip("fip-2", "other-port"),  # 다른 인스턴스
        _make_fip("fip-3", None),  # 미연결
    ]

    resp = await client.delete("/api/instances/inst-1/floating-ip")
    assert resp.status_code == 204

    called_ids = [call.args[0] for call in mock_conn.network.update_ip.call_args_list]
    assert called_ids == ["fip-1"], f"expected only fip-1 to be updated, got {called_ids}"
    called_delete_ids = [call.args[0] for call in mock_conn.network.delete_ip.call_args_list]
    assert called_delete_ids == ["fip-1"], f"expected only fip-1 to be deleted, got {called_delete_ids}"


@pytest.mark.asyncio
async def test_release_floating_ip_no_ports_does_nothing(client, mock_conn):
    """포트가 없는 인스턴스 해제 시 어떤 FIP도 건드리지 않는다."""
    mock_conn.network.ports.return_value = []

    resp = await client.delete("/api/instances/inst-1/floating-ip")
    assert resp.status_code == 204

    mock_conn.network.update_ip.assert_not_called()
    mock_conn.network.delete_ip.assert_not_called()


@pytest.mark.asyncio
async def test_delete_instance_only_cleans_own_fips(client, mock_conn):
    """인스턴스 삭제 시에도 해당 인스턴스 FIP만 정리된다 (다른 FIP 무사)."""
    inst = make_instance()
    inst.metadata = {}
    mock_conn.network.ports.return_value = [_make_port("p-inst")]
    mock_conn.network.ips.return_value = [
        _make_fip("fip-own", "p-inst"),
        _make_fip("fip-other", "p-other"),
    ]

    with (
        patch("app.api.compute.instances.nova.get_server", return_value=inst),
        patch("app.api.compute.instances.nova.delete_server", return_value=None),
        patch("app.api.compute.instances.cinder.delete_volume", return_value=None),
    ):
        resp = await client.delete("/api/instances/inst-1")
    assert resp.status_code == 204

    called_delete_ids = [call.args[0] for call in mock_conn.network.delete_ip.call_args_list]
    assert "fip-own" in called_delete_ids
    assert "fip-other" not in called_delete_ids


@pytest.mark.asyncio
async def test_release_floating_ip_per_fip_failure_isolated(client, mock_conn):
    """첫 FIP 정리 실패해도 두 번째 FIP는 정상 처리된다 (best-effort)."""
    mock_conn.network.ports.return_value = [_make_port("p1")]
    mock_conn.network.ips.return_value = [
        _make_fip("fip-fail", "p1"),
        _make_fip("fip-ok", "p1"),
    ]
    mock_conn.network.update_ip.side_effect = [Exception("Neutron 오류"), None]

    resp = await client.delete("/api/instances/inst-1/floating-ip")
    assert resp.status_code == 204

    update_calls = [call.args[0] for call in mock_conn.network.update_ip.call_args_list]
    assert update_calls == ["fip-fail", "fip-ok"]
