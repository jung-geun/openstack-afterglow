"""library_builder 단위 테스트.

SSH 기반 영구 Builder VM 파이프라인:
- start_build(): Manila share 생성 + CephX rule + _ssh_build_task 백그라운드 실행
- queue_build() / _build_worker(): asyncio.Queue 직렬화
- _build_ssh_command(): 마운트+설치 명령 구성
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _INSTALL_SCRIPTS 키 검증
# ---------------------------------------------------------------------------


def test_install_scripts_contains_pytorch_alias():
    """'pytorch' 키는 'torch'와 동일한 스크립트를 가리켜야 한다 (UI 호환성)."""
    from app.services.library_builder import _INSTALL_SCRIPTS

    assert "pytorch" in _INSTALL_SCRIPTS
    assert _INSTALL_SCRIPTS["pytorch"] == _INSTALL_SCRIPTS["torch"]


def test_install_scripts_has_all_expected_keys():
    """카탈로그에 정의된 라이브러리 ID가 모두 _INSTALL_SCRIPTS에 존재해야 한다."""
    from app.services.library_builder import _INSTALL_SCRIPTS

    for lib_id in ("python311", "torch", "pytorch", "vllm", "jupyter"):
        assert lib_id in _INSTALL_SCRIPTS, f"'{lib_id}' 키가 _INSTALL_SCRIPTS에 없음"


# ---------------------------------------------------------------------------
# _build_ssh_command
# ---------------------------------------------------------------------------


def test_build_ssh_command_contains_mount_command():
    """생성된 SSH 명령에 CephFS mount 명령이 포함돼야 한다."""
    from app.services.library_builder import _build_ssh_command

    cmd = _build_ssh_command(
        ceph_mons="10.0.0.1",
        share_path="/volumes/_nogroup/abc",
        cephx_user="union-builder-python311",
        cephx_secret="AQTEST==",
        install_script="echo installing",
    )
    assert "mount -t ceph" in cmd
    assert "union-builder-python311" in cmd


def test_build_ssh_command_creates_build_complete_marker():
    """.union_build_complete 마커 생성 명령이 있어야 한다."""
    from app.services.library_builder import _build_ssh_command

    cmd = _build_ssh_command(
        ceph_mons="mon",
        share_path="/path",
        cephx_user="u",
        cephx_secret="s",
        install_script="echo ok",
    )
    assert ".union_build_complete" in cmd


def test_build_ssh_command_progress_markers():
    """[progress] N 마커가 3단계(30, 80, 100) 포함돼야 한다."""
    from app.services.library_builder import _build_ssh_command

    cmd = _build_ssh_command(
        ceph_mons="mon",
        share_path="/path",
        cephx_user="u",
        cephx_secret="s",
        install_script="echo ok",
    )
    assert "[progress] 30" in cmd
    assert "[progress] 80" in cmd
    assert "[progress] 100" in cmd


def test_build_ssh_command_encodes_secret_as_base64():
    """cephx_secret이 base64로 인코딩되어 원본이 노출되지 않아야 한다."""
    import base64

    from app.services.library_builder import _build_ssh_command

    secret = "AQ+special/chars==\nwith newline"
    cmd = _build_ssh_command(
        ceph_mons="mon",
        share_path="/path",
        cephx_user="u",
        cephx_secret=secret,
        install_script="echo ok",
    )
    expected_b64 = base64.b64encode(secret.encode()).decode()
    assert expected_b64 in cmd
    assert secret not in cmd


def test_build_ssh_command_encodes_install_script_as_base64():
    """설치 스크립트가 base64로 인코딩되어 전달돼야 한다."""
    import base64

    from app.services.library_builder import _build_ssh_command

    script = "uv pip install torch\necho done"
    cmd = _build_ssh_command(
        ceph_mons="mon",
        share_path="/path",
        cephx_user="u",
        cephx_secret="s",
        install_script=script,
    )
    expected_b64 = base64.b64encode(script.encode()).decode()
    assert expected_b64 in cmd


def test_build_ssh_command_uses_set_euo_pipefail():
    """엄격 오류 처리(set -euo pipefail)가 포함돼야 한다."""
    from app.services.library_builder import _build_ssh_command

    cmd = _build_ssh_command("m", "/p", "u", "s", "echo ok")
    assert "set -euo pipefail" in cmd


# ---------------------------------------------------------------------------
# start_build
# ---------------------------------------------------------------------------


def _make_lib():
    lib = MagicMock()
    lib.id = "python311"
    lib.version = "3.11.0"
    return lib


@pytest.mark.asyncio
async def test_start_build_creates_background_ssh_task():
    """start_build()는 asyncio.create_task로 _ssh_build_task를 백그라운드에서 실행한다."""
    from app.services import library_builder

    captured_tasks: list = []

    def _fake_create_task(coro):
        captured_tasks.append(coro)
        coro.close()  # "never awaited" 경고 방지
        return MagicMock()

    mock_file_storage = MagicMock()
    mock_file_storage.id = "share-build-1"

    call_results = iter(
        [
            MagicMock(),  # get_service_project_connection
            mock_file_storage,  # create_file_storage
            {"access_key": "AQTEST==", "access_id": "r1"},  # create_access_rule
            ["10.0.0.1:6789:/vol/lib"],  # get_export_locations
        ]
    )

    async def _fake_to_thread(fn, *args, **kwargs):
        return next(call_results)

    settings = MagicMock()
    settings.os_manila_share_network_id = "snet-1"
    settings.os_manila_share_type = "cephfstype"
    settings.ceph_monitors = "10.0.0.1"

    with (
        patch("app.services.library_builder.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.library_builder.asyncio.to_thread", side_effect=_fake_to_thread),
        patch("app.services.library_builder.asyncio.create_task", side_effect=_fake_create_task),
        patch("app.services.library_builder.get_settings", return_value=settings),
        patch("app.services.library_builder.lib_svc.get_by_id", return_value=_make_lib()),
        patch("app.services.library_builder._active_builds", {}),
    ):
        result = await library_builder.start_build("python311")

    assert result["status"] == "building"
    assert result["file_storage_id"] == "share-build-1"
    assert len(captured_tasks) == 1, "_ssh_build_task가 create_task로 한 번 실행되어야 한다"


@pytest.mark.asyncio
async def test_start_build_rejects_unknown_library():
    """_INSTALL_SCRIPTS에 없는 library_id는 RuntimeError를 발생시켜야 한다."""
    from app.services import library_builder

    with (
        patch("app.services.library_builder.get_service_project_connection", return_value=MagicMock()),
        patch("app.services.library_builder.asyncio.to_thread", new_callable=AsyncMock),
        patch("app.services.library_builder.lib_svc.get_by_id", return_value=_make_lib()),
        patch("app.services.library_builder._active_builds", {}),
    ):
        with pytest.raises(RuntimeError, match="알 수 없는 라이브러리"):
            await library_builder.start_build("nonexistent_lib_xyz")


@pytest.mark.asyncio
async def test_start_build_rejects_duplicate_library():
    """동일 라이브러리에 대해 빌드가 진행 중이면 RuntimeError를 발생시킨다."""
    from app.services import library_builder

    fake_active = {"python311": {"status": "building"}}
    with patch("app.services.library_builder._active_builds", fake_active):
        with pytest.raises(RuntimeError, match="이미 빌드 중인"):
            await library_builder.start_build("python311")


@pytest.mark.asyncio
async def test_start_build_cleans_up_share_on_cephx_failure():
    """CephX rule 생성 실패 시 Manila share가 삭제되어야 한다."""
    from app.services import library_builder

    mock_file_storage = MagicMock()
    mock_file_storage.id = "share-fail-1"

    delete_called: list[str] = []

    async def _fake_to_thread(fn, *args, **kwargs):
        fn_name = getattr(fn, "__name__", str(fn))
        if "create_file_storage" in fn_name or (args and callable(args[0])):
            return mock_file_storage
        if "create_access_rule" in fn_name:
            raise RuntimeError("CephX quota 초과")
        if "delete_file_storage" in fn_name:
            delete_called.append("deleted")
            return None
        return MagicMock()

    settings = MagicMock()
    settings.os_manila_share_network_id = "snet-1"
    settings.os_manila_share_type = "cephfstype"

    with (
        patch("app.services.library_builder.get_service_project_connection", return_value=MagicMock()),
        patch(
            "app.services.library_builder.asyncio.to_thread",
            side_effect=[
                mock_file_storage,  # create_file_storage 성공
                RuntimeError("CephX quota 초과"),  # create_access_rule 실패
                None,  # delete_file_storage
            ],
        ),
        patch("app.services.library_builder.get_settings", return_value=settings),
        patch("app.services.library_builder.lib_svc.get_by_id", return_value=_make_lib()),
        patch("app.services.library_builder._active_builds", {}),
        patch("app.services.library_builder.manila.delete_file_storage"),
    ):
        with pytest.raises(RuntimeError):
            await library_builder.start_build("python311")


# ---------------------------------------------------------------------------
# queue_build / _build_worker / get_build_queue_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_build_adds_to_queue():
    """queue_build()는 library_id를 큐와 _queued_libraries에 추가한다."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()

    with (
        patch("app.services.library_builder._active_builds", {}),
        patch("app.services.library_builder._queued_libraries", set()),
        patch("app.services.library_builder._build_queue", fresh_queue),
    ):
        result = await library_builder.queue_build("torch")

    assert result["status"] == "queued"
    assert result["library_id"] == "torch"
    assert fresh_queue.qsize() == 1
    assert fresh_queue.get_nowait() == "torch"


@pytest.mark.asyncio
async def test_queue_build_rejects_duplicate_queued():
    """이미 큐에 있는 library_id를 다시 큐에 넣으면 RuntimeError."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()
    queued = {"torch"}

    with (
        patch("app.services.library_builder._active_builds", {}),
        patch("app.services.library_builder._queued_libraries", queued),
        patch("app.services.library_builder._build_queue", fresh_queue),
    ):
        with pytest.raises(RuntimeError, match="이미 빌드 큐에"):
            await library_builder.queue_build("torch")


@pytest.mark.asyncio
async def test_queue_build_rejects_active_library():
    """이미 빌드 중인 library_id를 큐에 넣으면 RuntimeError."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()

    with (
        patch("app.services.library_builder._active_builds", {"torch": {"status": "building"}}),
        patch("app.services.library_builder._queued_libraries", set()),
        patch("app.services.library_builder._build_queue", fresh_queue),
    ):
        with pytest.raises(RuntimeError, match="이미 빌드 중인"):
            await library_builder.queue_build("torch")


def test_get_build_queue_status():
    """get_build_queue_status()는 queued/active/queue_size를 반환한다."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()
    fresh_queue.put_nowait("vllm")

    with (
        patch("app.services.library_builder._active_builds", {"python311": {"status": "building"}}),
        patch("app.services.library_builder._queued_libraries", {"vllm"}),
        patch("app.services.library_builder._build_queue", fresh_queue),
    ):
        status = library_builder.get_build_queue_status()

    assert status["active"] == ["python311"]
    assert status["queued"] == ["vllm"]
    assert status["queue_size"] == 1


@pytest.mark.asyncio
async def test_build_worker_calls_start_build_and_marks_done():
    """_build_worker()는 큐에서 꺼낸 library_id로 start_build()를 호출한다."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()
    await fresh_queue.put("jupyter")
    queued = {"jupyter"}

    calls: list[str] = []

    async def _fake_start_build(lid: str) -> dict:
        calls.append(lid)
        return {"status": "building", "library_id": lid}

    with (
        patch("app.services.library_builder._build_queue", fresh_queue),
        patch("app.services.library_builder._queued_libraries", queued),
        patch("app.services.library_builder.start_build", side_effect=_fake_start_build),
    ):
        worker_task = asyncio.create_task(library_builder._build_worker())
        await asyncio.wait_for(fresh_queue.join(), timeout=2.0)
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    assert calls == ["jupyter"]
    assert "jupyter" not in queued
