"""Builder VM 관리 서비스.

영구 Builder VM(기존)과 빌드별 임시 Ephemeral Builder VM(신규) 두 가지를 모두 지원한다.
"""

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

_BUILDER_VM_NAME = "afterglow-builder"
_BUILDER_KEYPAIR_NAME = "afterglow-builder-key"

# 영구 Builder VM 최초 1회 실행되는 bootstrap cloud-init
_BOOTSTRAP_CLOUD_INIT = """\
#!/bin/bash
set -e
apt-get update -qq
apt-get install -y ceph-common python3-pip curl
curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh
mkdir -p /mnt/share
echo "[builder] ready" > /etc/motd
"""

# 프로세스 재시작 간 캐시 (단일 프로세스 내 재조회 방지)
_cached_endpoint: BuilderEndpoint | None = None


@dataclass
class BuilderEndpoint:
    server_id: str
    host: str
    username: str
    key_path: str


def invalidate_cache() -> None:
    """캐시된 endpoint를 무효화한다 (테스트 및 VM 교체 시 사용)."""
    global _cached_endpoint
    _cached_endpoint = None


async def ensure_builder_vm(svc_conn) -> BuilderEndpoint:
    """서비스 프로젝트에 영구 Builder VM이 존재하고 SSH로 도달 가능함을 보장한다."""
    global _cached_endpoint
    if _cached_endpoint is not None:
        return _cached_endpoint

    settings = get_settings()
    server = await _find_existing_server(svc_conn, settings)

    if server is None:
        endpoint = await _create_new_builder_vm(svc_conn, settings)
        _cached_endpoint = endpoint
        _logger.info(
            "[builder_vm] 영구 Builder VM 생성 완료: server_id=%s, fip=%s — "
            "config.toml [builder] persistent_server_id = %r 설정으로 재생성 방지 가능",
            endpoint.server_id,
            endpoint.host,
            endpoint.server_id,
        )
        return endpoint

    # SHUTOFF 상태 → 재시작
    if server.status == "SHUTOFF":
        _logger.info("[builder_vm] Builder VM SHUTOFF — 재시작: %s", server.id)
        await asyncio.to_thread(svc_conn.compute.start_server, server.id)
        await _wait_for_active(svc_conn, server.id)
        server = await asyncio.to_thread(svc_conn.compute.get_server, server.id)

    # ERROR 상태 → 새로 생성 (기존 VM은 유지, 새 이름으로 생성)
    if server.status == "ERROR":
        _logger.warning("[builder_vm] Builder VM ERROR 상태 — 신규 생성: %s", server.id)
        endpoint = await _create_new_builder_vm(svc_conn, settings)
        _cached_endpoint = endpoint
        return endpoint

    # BUILD 상태 → ACTIVE 대기
    if server.status == "BUILD":
        await _wait_for_active(svc_conn, server.id)
        server = await asyncio.to_thread(svc_conn.compute.get_server, server.id)

    host = settings.builder_ssh_host or _extract_fip(server)
    if not host:
        if not settings.builder_floating_network_id:
            raise RuntimeError(
                f"Builder VM {server.id}에 FIP가 없습니다. "
                "config.toml [builder] floating_network_id 또는 ssh_host를 설정하세요."
            )
        host = await _ensure_fip(svc_conn, server.id, settings.builder_floating_network_id)

    endpoint = BuilderEndpoint(
        server_id=server.id,
        host=host,
        username=settings.builder_ssh_user,
        key_path=settings.builder_ssh_key_path,
    )
    _cached_endpoint = endpoint
    return endpoint


async def _find_existing_server(svc_conn, settings) -> object | None:
    """설정 server_id 또는 이름으로 기존 Builder VM을 찾는다."""
    # 1. 설정에서 server_id 직접 조회
    server_id = settings.builder_persistent_server_id
    if server_id:
        try:
            server = await asyncio.to_thread(svc_conn.compute.get_server, server_id)
            if server is not None:
                return server
        except Exception:
            _logger.warning("[builder_vm] 설정 server_id %s 조회 실패, 이름으로 탐색", server_id)

    # 2. 이름으로 탐색 (afterglow-builder*)
    try:
        candidates = await asyncio.to_thread(
            lambda: list(svc_conn.compute.servers(name=_BUILDER_VM_NAME))
        )
        # ACTIVE > BUILD > SHUTOFF 우선순위로 정렬
        priority = {"ACTIVE": 0, "BUILD": 1, "SHUTOFF": 2}
        candidates.sort(key=lambda s: priority.get(s.status, 9))
        if candidates:
            return candidates[0]
    except Exception:
        _logger.warning("[builder_vm] 서버 이름 탐색 실패", exc_info=True)

    return None


async def _create_new_builder_vm(svc_conn, settings) -> BuilderEndpoint:
    """새 영구 Builder VM을 생성하고 SSH 도달 확인 후 BuilderEndpoint를 반환한다."""
    image_id = settings.builder_image_id
    flavor_id = settings.builder_flavor_id
    network_id = settings.builder_network_id or settings.default_network_id

    if not image_id or not flavor_id:
        raise RuntimeError(
            "Builder VM 설정이 없습니다 (config.toml [builder] image_id, flavor_id 필요)"
        )

    keypair_name = await _ensure_keypair(svc_conn, settings.builder_ssh_key_path)
    userdata_b64 = base64.b64encode(_BOOTSTRAP_CLOUD_INIT.encode()).decode()

    server = await asyncio.to_thread(
        svc_conn.compute.create_server,
        name=_BUILDER_VM_NAME,
        image_id=image_id,
        flavor_id=flavor_id,
        networks=[{"uuid": network_id}],
        user_data=userdata_b64,
        key_name=keypair_name,
        metadata={"union_type": "builder", "afterglow_managed": "true"},
    )
    server_id = server.id
    _logger.info("[builder_vm] Builder VM 생성 중: %s", server_id)

    await _wait_for_active(svc_conn, server_id)

    host = settings.builder_ssh_host
    if not host:
        if not settings.builder_floating_network_id:
            raise RuntimeError(
                "config.toml [builder] floating_network_id 또는 ssh_host를 설정하세요."
            )
        host = await _ensure_fip(svc_conn, server_id, settings.builder_floating_network_id)

    await _wait_for_ssh(host, settings.builder_ssh_key_path, settings.builder_ssh_user)

    return BuilderEndpoint(
        server_id=server_id,
        host=host,
        username=settings.builder_ssh_user,
        key_path=settings.builder_ssh_key_path,
    )


async def _ensure_keypair(svc_conn, key_path: str) -> str:
    """Nova keypair 존재를 확인하고 없으면 생성해 개인키를 key_path에 저장한다."""
    keypair = None
    try:
        keypair = await asyncio.to_thread(svc_conn.compute.get_keypair, _BUILDER_KEYPAIR_NAME)
    except Exception:
        pass

    if keypair is not None and os.path.exists(key_path):
        return _BUILDER_KEYPAIR_NAME

    if keypair is None:
        kp = await asyncio.to_thread(
            svc_conn.compute.create_keypair,
            name=_BUILDER_KEYPAIR_NAME,
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
        _logger.info("[builder_vm] SSH 키페어 생성 및 저장: %s", key_path)
    else:
        raise RuntimeError(
            f"Nova keypair '{_BUILDER_KEYPAIR_NAME}'는 존재하지만 "
            f"개인키 파일이 없습니다: {key_path}\n"
            "K8s 환경: Secret 볼륨으로 마운트되어야 합니다."
        )

    return _BUILDER_KEYPAIR_NAME


def _extract_fip(server) -> str | None:
    """서버 addresses에서 Floating IP를 추출한다."""
    for network_addrs in (server.addresses or {}).values():
        for addr in network_addrs:
            if addr.get("OS-EXT-IPS:type") == "floating":
                return addr["addr"]
    return None


async def _ensure_fip(svc_conn, server_id: str, floating_network_id: str) -> str:
    """서버에 FIP를 할당한다. 이미 있으면 그대로 반환한다."""
    server = await asyncio.to_thread(svc_conn.compute.get_server, server_id)
    existing = _extract_fip(server)
    if existing:
        return existing

    fip = await asyncio.to_thread(
        svc_conn.network.create_ip,
        floating_network_id=floating_network_id,
    )
    await asyncio.to_thread(
        svc_conn.compute.add_floating_ip_to_server,
        server_id,
        fip.floating_ip_address,
    )
    _logger.info("[builder_vm] FIP 할당: %s → %s", server_id, fip.floating_ip_address)
    return fip.floating_ip_address


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
                host, key_path, "echo ok",
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
    host: str         # FIP 주소 (SSH 접속용)
    username: str
    key_path: str
    internal_ip: str  # Fixed IP (NFS access rule 등록용)
    fip_id: str       # FIP ID (삭제용)


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _extract_fixed_ip(server) -> str | None:
    """서버 addresses에서 Fixed(internal) IP를 추출한다."""
    for network_addrs in (server.addresses or {}).values():
        for addr in network_addrs:
            if addr.get("OS-EXT-IPS:type") == "fixed":
                return addr["addr"]
    return None


async def _allocate_new_fip(svc_conn, server_id: str, floating_network_id: str) -> tuple[str, str]:
    """FIP를 새로 생성해 서버에 붙이고 (addr, fip_id)를 반환한다."""
    fip = await asyncio.to_thread(
        svc_conn.network.create_ip,
        floating_network_id=floating_network_id,
    )
    await asyncio.to_thread(
        svc_conn.compute.add_floating_ip_to_server,
        server_id,
        fip.floating_ip_address,
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

    image_id = settings.builder_image_id
    flavor_id = settings.builder_flavor_id
    network_id = settings.builder_network_id or settings.default_network_id

    if not image_id or not flavor_id:
        raise RuntimeError(
            "Ephemeral Builder VM 설정이 없습니다 (config.toml [builder] image_id, flavor_id 필요)"
        )
    if not settings.builder_floating_network_id:
        raise RuntimeError(
            "config.toml [builder] floating_network_id가 필요합니다 (ephemeral VM SSH 접속용)"
        )

    keypair_name = await _ensure_keypair(svc_conn, settings.builder_ssh_key_path)
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

    fip_addr, fip_id = await _allocate_new_fip(
        svc_conn, server_id, settings.builder_floating_network_id
    )

    await _wait_for_ssh(fip_addr, settings.builder_ssh_key_path, settings.builder_ssh_user)

    _logger.info(
        "[ephemeral_vm] VM 준비 완료: server_id=%s, fip=%s, internal_ip=%s",
        server_id,
        fip_addr,
        internal_ip,
    )
    return EphemeralBuilderVM(
        server_id=server_id,
        host=fip_addr,
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
