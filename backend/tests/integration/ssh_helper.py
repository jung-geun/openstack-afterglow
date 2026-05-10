"""SSH 검증 헬퍼 — 통합 테스트가 VM 내부 상태를 직접 확인할 때 사용.

health endpoint(`/api/instances/{id}/health`)는 VM agent의 자체 보고에 의존하므로,
agent가 거짓 보고하면 회귀를 못 잡는다. 본 헬퍼는 SSH로 직접 명령을 실행해
독립된 시그널을 확보한다.

paramiko 의존성 회피 — self-hosted runner에 항상 존재하는 `ssh` 바이너리 사용.

실행 예:
    from tests.integration.ssh_helper import wait_for_ssh, verify_overlay_mount
    wait_for_ssh("10.0.0.5", "/path/to/key")
    assert verify_overlay_mount("10.0.0.5", "/path/to/key")
"""

from __future__ import annotations

import asyncio
import shlex
import subprocess
import time

_DEFAULT_OPTS = (
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "LogLevel=ERROR",
)


def _build_cmd(host: str, key_path: str, user: str, remote_cmd: str) -> list[str]:
    return [
        "ssh",
        "-i",
        key_path,
        *_DEFAULT_OPTS,
        f"{user}@{host}",
        remote_cmd,
    ]


def ssh_run(
    host: str,
    key_path: str,
    cmd: str,
    user: str = "ubuntu",
    timeout: int = 30,
) -> tuple[int, str, str]:
    """원격 명령 실행. (rc, stdout, stderr) 반환.

    BatchMode=yes로 패스워드 프롬프트 차단 — CI에서 행 방지.
    StrictHostKeyChecking=no + UserKnownHostsFile=/dev/null로 호스트 키 자동 수락.
    """
    proc = subprocess.run(
        _build_cmd(host, key_path, user, cmd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def wait_for_ssh(
    host: str,
    key_path: str,
    user: str = "ubuntu",
    timeout: int = 300,
    interval: int = 5,
) -> bool:
    """SSH 접속 가능 시점까지 폴링. 성공 시 True, 타임아웃 시 False.

    cloud-init 완료 후 sshd 기동까지 시간이 필요하므로 통합 테스트의
    VM 생성 직후 단계에서 사용한다.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rc, _, _ = ssh_run(host, key_path, "true", user=user, timeout=interval + 5)
            if rc == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
        time.sleep(interval)
    return False


async def wait_for_ssh_async(
    host: str,
    key_path: str,
    user: str = "ubuntu",
    timeout: int = 300,
    interval: int = 5,
) -> bool:
    """asyncio 버전 — 다중 VM 동시 부팅 검증에서 사용."""
    return await asyncio.to_thread(wait_for_ssh, host, key_path, user, timeout, interval)


def verify_overlay_mount(
    host: str,
    key_path: str,
    mount_path: str = "/opt/layers/merged",
    user: str = "ubuntu",
) -> bool:
    """`mountpoint -q $path` rc 검사. 마운트되어 있으면 True."""
    rc, _, _ = ssh_run(host, key_path, f"mountpoint -q {shlex.quote(mount_path)}", user=user)
    return rc == 0


def verify_nfs_mounts(
    host: str,
    key_path: str,
    expected_min_count: int,
    user: str = "ubuntu",
) -> bool:
    """현재 NFS 마운트 개수가 expected_min_count 이상이면 True."""
    rc, stdout, _ = ssh_run(host, key_path, "mount", user=user, timeout=15)
    if rc != 0:
        return False
    nfs_lines = [line for line in stdout.splitlines() if " type nfs" in line or " type nfs4" in line]
    return len(nfs_lines) >= expected_min_count


def verify_envmgr_status(host: str, key_path: str, user: str = "ubuntu") -> dict:
    """`envmgr-use --status` 출력 파싱. envmgr 미설치 시 빈 dict 반환."""
    rc, stdout, _ = ssh_run(host, key_path, "envmgr-use --status 2>/dev/null || true", user=user)
    if rc != 0 or not stdout.strip():
        return {}
    info: dict[str, str] = {}
    for line in stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip().lower()] = v.strip()
    return info
