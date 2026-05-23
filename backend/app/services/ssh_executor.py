"""asyncssh 기반 SSH 명령 실행기."""

from __future__ import annotations

import asyncio
import logging

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


