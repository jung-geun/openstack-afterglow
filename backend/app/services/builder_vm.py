"""Builder VM 관리 서비스 — Ephemeral (빌드별 임시) 경로만 지원."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import stat
import uuid
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

_EPHEMERAL_KEYPAIR_NAME = "afterglow-ephemeral-key"

_EPHEMERAL_CLOUD_INIT = """\
#!/bin/bash
set -e
apt-get update -qq
apt-get install -y --no-install-recommends nfs-common ceph-common
"""


@dataclass
class EphemeralBuilderVM:
    server_id: str
    host: str  # FIP 주소 (SSH 접속용)
    username: str
    key_path: str
    internal_ip: str  # Fixed IP (NFS access rule 등록용)
    fip_id: str  # FIP ID (삭제용)


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


async def _ensure_ephemeral_keypair(svc_conn, key_path: str) -> str:
    """Ephemeral VM 전용 키페어를 보장한다. 영구 Builder 키페어와 분리된다.

    키페어가 없으면 새로 생성하고 key_path에 저장한다.
    키페어는 있으나 로컬 파일이 없으면 기존 키페어를 삭제하고 재생성한다.
    """
    keypair = None
    try:
        keypair = await asyncio.to_thread(svc_conn.compute.get_keypair, _EPHEMERAL_KEYPAIR_NAME)
    except Exception:
        pass

    if keypair is not None and os.path.exists(key_path):
        return _EPHEMERAL_KEYPAIR_NAME

    if keypair is not None and not os.path.exists(key_path):
        # 키페어는 존재하지만 로컬 파일 없음 → 삭제 후 재생성
        _logger.warning(
            "[ephemeral_vm] 키페어 %s가 존재하지만 로컬 파일 없음(%s) — 키페어 재생성",
            _EPHEMERAL_KEYPAIR_NAME,
            key_path,
        )
        try:
            await asyncio.to_thread(svc_conn.compute.delete_keypair, _EPHEMERAL_KEYPAIR_NAME)
        except Exception:
            pass
        keypair = None

    # 새 키페어 생성
    kp = await asyncio.to_thread(
        svc_conn.compute.create_keypair,
        name=_EPHEMERAL_KEYPAIR_NAME,
    )
    private_key = kp.private_key
    if not private_key:
        raise RuntimeError("Nova keypair에서 private key를 받지 못했습니다")

    key_dir = os.path.dirname(key_path)
    if key_dir:
        os.makedirs(key_dir, exist_ok=True)
    with open(key_path, "w") as f:
        f.write(private_key)
    os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
    _logger.info("[ephemeral_vm] SSH 키페어 생성 및 저장: %s → %s", _EPHEMERAL_KEYPAIR_NAME, key_path)
    return _EPHEMERAL_KEYPAIR_NAME


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


async def create_ephemeral_vm(svc_conn) -> EphemeralBuilderVM:
    """service 프로젝트에 임시 Builder VM을 생성하고 SSH 도달 상태를 확인해 반환한다.

    cloud-init으로 nfs-common과 ceph-common을 설치한 뒤 SSH 연결이 확인되면 반환한다.
    VM은 호출자가 사용 후 delete_ephemeral_vm()으로 정리해야 한다.
    """
    settings = get_settings()

    from app.services import resource_policy_store
    from app.services.resource_policies import ResourcePolicyValidationError

    try:
        policies = await resource_policy_store.resolve_policies(
            conn=svc_conn,
            keys=("builder.image", "builder.flavor", "builder.network"),
        )
    except (ResourcePolicyValidationError, resource_policy_store.ResourcePolicyStorageUnavailable) as exc:
        raise RuntimeError("임시 빌더 리소스 정책이 유효하지 않습니다") from exc
    image_id = policies["builder.image"]
    flavor_id = policies["builder.flavor"]
    network_id = policies["builder.network"]

    keypair_name = await _ensure_ephemeral_keypair(svc_conn, settings.builder_ssh_key_path)
    userdata_b64 = base64.b64encode(_EPHEMERAL_CLOUD_INIT.encode()).decode()

    vm_name = f"afterglow-builder-{_short_id()}"
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
    _logger.info("[ephemeral_vm] VM 생성 중: %s (%s)", vm_name, server_id)

    await _wait_for_active(svc_conn, server_id)
    server = await asyncio.to_thread(svc_conn.compute.get_server, server_id)

    internal_ip = _extract_fixed_ip(server)
    if not internal_ip:
        raise RuntimeError(f"Ephemeral Builder VM {server_id}: internal IP를 찾을 수 없습니다")

    # FIP가 설정된 경우만 할당; 없으면 provider 네트워크 fixed IP를 직접 사용
    if settings.builder_floating_network_id:
        fip_addr, fip_id = await _allocate_new_fip(svc_conn, server_id, settings.builder_floating_network_id)
        ssh_host = fip_addr
    else:
        fip_addr, fip_id = internal_ip, None
        ssh_host = internal_ip

    await _wait_for_ssh(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)
    await _wait_for_cloud_init(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)

    _logger.info(
        "[ephemeral_vm] VM 준비 완료: server_id=%s, host=%s, internal_ip=%s",
        server_id,
        ssh_host,
        internal_ip,
    )
    return EphemeralBuilderVM(
        server_id=server_id,
        host=ssh_host,
        username=settings.builder_ssh_user,
        key_path=settings.builder_ssh_key_path,
        internal_ip=internal_ip,
        fip_id=fip_id,
    )


async def delete_ephemeral_vm(svc_conn, server_id: str, fip_id: str | None) -> None:
    """임시 Builder VM과 FIP를 정리한다. 각 단계는 best-effort로 처리한다."""
    if fip_id:
        try:
            await asyncio.to_thread(svc_conn.network.delete_ip, fip_id)
            _logger.info("[ephemeral_vm] FIP 반납: %s", fip_id)
        except Exception:
            _logger.warning("[ephemeral_vm] FIP 반납 실패: %s", fip_id, exc_info=True)

    try:
        await asyncio.to_thread(svc_conn.compute.delete_server, server_id)
        _logger.info("[ephemeral_vm] VM 삭제: %s", server_id)
    except Exception:
        _logger.warning("[ephemeral_vm] VM 삭제 실패: %s", server_id, exc_info=True)
