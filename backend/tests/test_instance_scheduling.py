"""VM 생성 시 스케줄링(HA/standard) metadata 단위 테스트."""

from unittest.mock import MagicMock

from app.models.compute import CreateInstanceRequest, InstanceInfo

# ─── 모델 기본값 ───────────────────────────────────────────────────────────────


def test_create_instance_request_scheduling_default_standard():
    """scheduling 미지정 시 기본값 standard."""
    req = CreateInstanceRequest(name="test-vm", image_id="img-1", flavor_id="f1")
    assert req.scheduling == "standard"


def test_create_instance_request_scheduling_ha():
    """scheduling=ha 지정 가능."""
    req = CreateInstanceRequest(name="test-vm", image_id="img-1", flavor_id="f1", scheduling="ha")
    assert req.scheduling == "ha"


# ─── _server_to_info metadata 파싱 ────────────────────────────────────────────


def _make_mock_server(meta: dict) -> MagicMock:
    s = MagicMock()
    s.id = "srv-1"
    s.name = "test"
    s.status = "ACTIVE"
    s.addresses = {}
    s.metadata = meta
    s.image = {"id": "img-1"}
    s.flavor = {"id": "f1", "original_name": "m1.small"}
    s.created_at = None
    s.key_name = None
    s.user_id = None
    s.project_id = "proj-1"
    s.tenant_id = None
    s.fault = None
    return s


def test_server_to_info_reads_scheduling_ha():
    """_server_to_info 가 metadata.scheduling=ha 를 InstanceInfo 에 채운다."""
    from app.services.nova import _server_to_info

    s = _make_mock_server({"scheduling": "ha", "HA_Enabled": "True"})
    info = _server_to_info(s)
    assert info.scheduling == "ha"


def test_server_to_info_reads_scheduling_standard():
    from app.services.nova import _server_to_info

    s = _make_mock_server({"scheduling": "standard"})
    info = _server_to_info(s)
    assert info.scheduling == "standard"


def test_server_to_info_scheduling_missing_returns_none():
    """이전 인스턴스(scheduling metadata 없음)는 None."""
    from app.services.nova import _server_to_info

    s = _make_mock_server({})
    info = _server_to_info(s)
    assert info.scheduling is None


# ─── InstanceInfo 모델 기본값 ──────────────────────────────────────────────────


def test_instance_info_scheduling_default_none():
    """InstanceInfo.scheduling 기본값은 None (기존 인스턴스 호환)."""
    info = InstanceInfo(id="i", name="n", status="ACTIVE")
    assert info.scheduling is None
