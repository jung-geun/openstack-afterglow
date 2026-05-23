"""ssh_executor 단위 테스트.

asyncssh를 mock으로 대체해 run_command / stream_command 동작을 검증한다.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_command_returns_exit_code_stdout_stderr():
    """정상 실행 시 (exit_code, stdout, stderr) 3-tuple을 반환한다."""
    mock_result = MagicMock()
    mock_result.exit_status = 0
    mock_result.stdout = "hello\n"
    mock_result.stderr = ""

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ssh_executor.asyncssh.connect", return_value=mock_ctx):
        from app.services.ssh_executor import run_command

        rc, stdout, stderr = await run_command("10.0.0.1", "/tmp/key", "echo hello")

    assert rc == 0
    assert stdout == "hello\n"
    assert stderr == ""


@pytest.mark.asyncio
async def test_run_command_non_zero_exit_code():
    """명령이 실패하면 0이 아닌 exit_code를 반환해야 한다."""
    mock_result = MagicMock()
    mock_result.exit_status = 1
    mock_result.stdout = ""
    mock_result.stderr = "command not found\n"

    mock_conn = AsyncMock()
    mock_conn.run = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ssh_executor.asyncssh.connect", return_value=mock_ctx):
        from app.services.ssh_executor import run_command

        rc, stdout, stderr = await run_command("10.0.0.1", "/tmp/key", "bad_cmd")

    assert rc == 1
    assert "not found" in stderr


# ---------------------------------------------------------------------------
# stream_command
# ---------------------------------------------------------------------------


def _make_async_iter(items: list[str]):
    """문자열 리스트를 async iterator로 변환하는 헬퍼."""

    class _AsyncIter:
        def __init__(self, data):
            self._data = iter(data)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._data)
            except StopIteration:
                raise StopAsyncIteration

    return _AsyncIter(items)


@pytest.mark.asyncio
async def test_stream_command_calls_callback_per_line():
    """stdout 라인마다 line_callback이 호출되어야 한다."""
    collected: list[str] = []

    mock_proc = MagicMock()
    mock_proc.stdout = _make_async_iter(["line1\n", "line2\n", "[progress] 50 halfway\n"])
    mock_proc.stderr = _make_async_iter([])
    mock_proc.exit_status = 0
    mock_proc.wait = AsyncMock(return_value=None)

    mock_proc_ctx = AsyncMock()
    mock_proc_ctx.__aenter__ = AsyncMock(return_value=mock_proc)
    mock_proc_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.create_process = MagicMock(return_value=mock_proc_ctx)

    mock_conn_ctx = AsyncMock()
    mock_conn_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ssh_executor.asyncssh.connect", return_value=mock_conn_ctx):
        from app.services.ssh_executor import stream_command

        rc, stderr = await stream_command(
            "10.0.0.1",
            "/tmp/key",
            "some cmd",
            line_callback=lambda line: collected.append(line),
        )

    assert rc == 0
    assert collected == ["line1", "line2", "[progress] 50 halfway"]
    assert stderr == ""


@pytest.mark.asyncio
async def test_stream_command_returns_stderr():
    """stderr 출력이 반환값에 포함되어야 한다."""
    mock_proc = MagicMock()
    mock_proc.stdout = _make_async_iter([])
    mock_proc.stderr = _make_async_iter(["error line\n"])
    mock_proc.exit_status = 2
    mock_proc.wait = AsyncMock(return_value=None)

    mock_proc_ctx = AsyncMock()
    mock_proc_ctx.__aenter__ = AsyncMock(return_value=mock_proc)
    mock_proc_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.create_process = MagicMock(return_value=mock_proc_ctx)

    mock_conn_ctx = AsyncMock()
    mock_conn_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.ssh_executor.asyncssh.connect", return_value=mock_conn_ctx):
        from app.services.ssh_executor import stream_command

        rc, stderr = await stream_command(
            "10.0.0.1",
            "/tmp/key",
            "bad cmd",
            line_callback=lambda line: None,
        )

    assert rc == 2
    assert "error line" in stderr
