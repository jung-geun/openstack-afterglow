"""asyncssh 기반 SSH 명령 실행기."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import asyncssh

_logger = logging.getLogger(__name__)


async def run_command(
    host: str,
    key_path: str,
    command: str,
    *,
    username: str = "ubuntu",
    timeout: int = 3600,
    connect_timeout: int = 30,
) -> tuple[int, str, str]:
    """SSH로 단일 명령을 실행하고 (exit_code, stdout, stderr)를 반환한다."""
    async with asyncssh.connect(
        host,
        username=username,
        client_keys=[key_path],
        known_hosts=None,
        connect_timeout=connect_timeout,
    ) as conn:
        result = await asyncio.wait_for(
            conn.run(command, check=False),
            timeout=timeout,
        )
        return result.exit_status or 0, result.stdout or "", result.stderr or ""


async def stream_command(
    host: str,
    key_path: str,
    command: str,
    line_callback: Callable[[str], None],
    *,
    username: str = "ubuntu",
    timeout: int = 3600,
    connect_timeout: int = 30,
) -> tuple[int, str]:
    """SSH로 명령을 실행하며 stdout 라인마다 line_callback을 호출한다.

    Returns: (exit_code, stderr)
    """
    stderr_lines: list[str] = []

    async with asyncssh.connect(  # noqa: SIM117
        host,
        username=username,
        client_keys=[key_path],
        known_hosts=None,
        connect_timeout=connect_timeout,
    ) as conn:
        async with conn.create_process(command) as proc:
            async def _collect_stderr() -> None:
                async for line in proc.stderr:
                    stderr_lines.append(line)

            try:
                async with asyncio.timeout(timeout):
                    stderr_task = asyncio.create_task(_collect_stderr())
                    try:
                        async for raw_line in proc.stdout:
                            line_callback(raw_line.rstrip("\n"))
                    finally:
                        await stderr_task
                    await proc.wait()
            except TimeoutError:
                proc.kill()
                raise

            exit_code = proc.exit_status
            if exit_code is None:
                raise RuntimeError("SSH 프로세스 종료 코드를 알 수 없습니다 (신호로 강제 종료됐을 수 있음)")

    return exit_code, "".join(stderr_lines)
