"""Builder VM 관리 서비스 — Ephemeral (빌드별 임시) 경로만 지원."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import stat
import tempfile
import uuid
from contextlib import suppress
from dataclasses import dataclass

from app.config import get_settings

_logger = logging.getLogger(__name__)


async def _wait_for_active(svc_conn, server_id: str, timeout_seconds: int = 600) -> None:
    """서버가 ACTIVE 상태가 될 때까지 폴링한다."""
    for _ in range(timeout_seconds // 10):
        await asyncio.sleep(10)
        server = await asyncio.to_thread(svc_conn.compute.get_server, server_id)
        if server.status == "ACTIVE":
            return
        if server.status == "ERROR":
            raise RuntimeError(f"Builder VM {server_id}가 ERROR 상태로 전환됨")
    raise TimeoutError(f"Builder VM {server_id}가 {timeout_seconds}초 내 ACTIVE 상태가 되지 않음")


async def _wait_for_ssh(
    host: str,
    key_path: str,
    username: str,
    timeout_seconds: int = 120,
) -> None:
    """SSH가 도달 가능해질 때까지 폴링한다."""
    from app.services.ssh_executor import run_command

    for _ in range(timeout_seconds // 10):
        await asyncio.sleep(10)
        try:
            rc, _, _ = await run_command(
                host,
                key_path,
                "echo ok",
                username=username,
                connect_timeout=5,
                timeout=10,
            )
            if rc == 0:
                _logger.info("[builder_vm] SSH 도달 확인: %s", host)
                return
        except Exception:
            pass
    raise TimeoutError(f"Builder VM SSH 도달 불가: {host} ({timeout_seconds}초 초과)")


async def _wait_for_cloud_init(
    host: str,
    key_path: str,
    username: str,
    timeout_seconds: int = 300,
) -> None:
    """cloud-init이 완료될 때까지 기다린다 (nfs-common/ceph-common 설치 완료 보장)."""
    from app.services.ssh_executor import run_command

    _logger.info("[builder_vm] cloud-init 완료 대기: %s", host)
    for _ in range(timeout_seconds // 10):
        await asyncio.sleep(10)
        try:
            rc, stdout, _ = await run_command(
                host,
                key_path,
                "cloud-init status",
                username=username,
                timeout=10,
            )
            if rc == 0 and ("done" in stdout or "disabled" in stdout):
                _logger.info("[builder_vm] cloud-init 완료: %s", host)
                return
            if "error" in stdout:
                _logger.warning("[builder_vm] cloud-init 오류: %s", stdout.strip())
                return
        except Exception:
            pass
    _logger.warning("[builder_vm] cloud-init 완료 대기 시간 초과: %s", host)


# ---------------------------------------------------------------------------
# Ephemeral Builder VM — 빌드마다 새로 생성·삭제
# ---------------------------------------------------------------------------

_EPHEMERAL_CLOUD_INIT = """\
#!/bin/bash
set -e
apt-get update -qq
apt-get install -y --no-install-recommends nfs-common ceph-common
"""


@dataclass
class EphemeralBuilderVM:
    server_id: str
    host: str
    username: str
    key_path: str
    keypair_name: str
    internal_ip: str
    fip_id: str | None


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


async def _create_one_use_keypair(svc_conn) -> tuple[str, str]:
    """Create a unique Nova keypair and an owner-only temporary private key."""
    keypair_name = f"afterglow-palimpsest-{_short_id()}"
    keypair = await asyncio.to_thread(svc_conn.compute.create_keypair, name=keypair_name)
    private_key = getattr(keypair, "private_key", None)
    if not private_key:
        with suppress(Exception):
            await asyncio.to_thread(svc_conn.compute.delete_keypair, keypair_name)
        raise RuntimeError("Nova keypair did not return private key material")

    fd, key_path = tempfile.mkstemp(prefix="afterglow-palimpsest-", suffix=".key")
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        os.write(fd, private_key.encode())
    finally:
        os.close(fd)
    return keypair_name, key_path


def _extract_fixed_ip(server) -> str | None:
    """서버 addresses에서 Fixed(internal) IP를 추출한다."""
    for network_addrs in (server.addresses or {}).values():
        for addr in network_addrs:
            if addr.get("OS-EXT-IPS:type") == "fixed":
                return addr["addr"]
    return None


async def _allocate_new_fip(svc_conn, server_id: str, floating_network_id: str) -> tuple[str, str]:
    """FIP를 새로 생성해 서버에 붙이고 (addr, fip_id)를 반환한다."""
    ports = await asyncio.to_thread(lambda: list(svc_conn.network.ports(device_id=server_id)))
    if not ports:
        raise RuntimeError(f"서버 {server_id}에 네트워크 포트가 없습니다")

    fip = await asyncio.to_thread(
        svc_conn.network.create_ip,
        floating_network_id=floating_network_id,
        port_id=ports[0].id,
    )
    _logger.info(
        "[ephemeral_vm] FIP 할당: %s → %s (fip_id=%s)",
        server_id,
        fip.floating_ip_address,
        fip.id,
    )
    return fip.floating_ip_address, fip.id


async def create_ephemeral_vm(
    svc_conn,
    *,
    image_id: str,
    flavor_id: str,
    network_id: str,
    floating_network_id: str | None = None,
) -> EphemeralBuilderVM:
    """Create a one-use Palimpsest utility VM from an immutable job snapshot."""
    if not all((image_id, flavor_id, network_id)):
        raise ValueError("image_id, flavor_id, and network_id are required for an ephemeral Builder VM")

    settings = get_settings()
    keypair_name = ""
    key_path = ""
    server_id: str | None = None
    fip_id: str | None = None
    try:
        keypair_name, key_path = await _create_one_use_keypair(svc_conn)
        userdata_b64 = base64.b64encode(_EPHEMERAL_CLOUD_INIT.encode()).decode()
        vm_name = f"afterglow-palimpsest-{_short_id()}"
        server = await asyncio.to_thread(
            svc_conn.compute.create_server,
            name=vm_name,
            image_id=image_id,
            flavor_id=flavor_id,
            networks=[{"uuid": network_id}],
            user_data=userdata_b64,
            key_name=keypair_name,
            metadata={"union_type": "ephemeral-builder", "afterglow_managed": "true"},
        )
        server_id = server.id
        await _wait_for_active(svc_conn, server_id)
        server = await asyncio.to_thread(svc_conn.compute.get_server, server_id)
        internal_ip = _extract_fixed_ip(server)
        if not internal_ip:
            raise RuntimeError(f"Ephemeral Builder VM {server_id}: internal IP를 찾을 수 없습니다")

        ssh_host = internal_ip
        if floating_network_id:
            ssh_host, fip_id = await _allocate_new_fip(svc_conn, server_id, floating_network_id)

        await _wait_for_ssh(ssh_host, key_path, settings.builder_ssh_user)
        await _wait_for_cloud_init(ssh_host, key_path, settings.builder_ssh_user)
        return EphemeralBuilderVM(
            server_id=server_id,
            host=ssh_host,
            username=settings.builder_ssh_user,
            key_path=key_path,
            keypair_name=keypair_name,
            internal_ip=internal_ip,
            fip_id=fip_id,
        )
    except Exception:
        await delete_ephemeral_vm(
            svc_conn,
            server_id=server_id,
            fip_id=fip_id,
            keypair_name=keypair_name or None,
            key_path=key_path or None,
        )
        raise


async def delete_ephemeral_vm(
    svc_conn,
    *,
    server_id: str | None,
    fip_id: str | None,
    keypair_name: str | None,
    key_path: str | None,
) -> None:
    """Best-effort cleanup for every one-use VM resource, including local key material."""
    if fip_id:
        with suppress(Exception):
            await asyncio.to_thread(svc_conn.network.delete_ip, fip_id)
    if server_id:
        with suppress(Exception):
            await asyncio.to_thread(svc_conn.compute.delete_server, server_id)
    if keypair_name:
        with suppress(Exception):
            await asyncio.to_thread(svc_conn.compute.delete_keypair, keypair_name)
    if key_path:
        with suppress(FileNotFoundError):
            os.unlink(key_path)
