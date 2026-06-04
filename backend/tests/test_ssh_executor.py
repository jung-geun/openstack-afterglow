"""ssh_executor 단위 테스트.

asyncssh를 mock으로 대체해 run_command 동작을 검증한다.
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
