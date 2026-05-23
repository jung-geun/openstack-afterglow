"""library_builder 단위 테스트.

Ephemeral 빌드 파이프라인:
- queue_build() / _build_worker(): asyncio.Queue 직렬화
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
async def test_build_worker_calls_start_ephemeral_build_and_marks_done():
    """_build_worker()는 큐에서 꺼낸 library_id로 start_ephemeral_build()를 호출한다."""
    import asyncio

    from app.services import library_builder

    fresh_queue: asyncio.Queue[str] = asyncio.Queue()
    await fresh_queue.put("jupyter")
    queued = {"jupyter"}

    calls: list[str] = []

    async def _fake_start_ephemeral(lid: str) -> dict:
        calls.append(lid)
        return {"status": "building", "library_id": lid}

    with (
        patch("app.services.library_builder._build_queue", fresh_queue),
        patch("app.services.library_builder._queued_libraries", queued),
        patch("app.services.library_builder.start_ephemeral_build", side_effect=_fake_start_ephemeral),
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
