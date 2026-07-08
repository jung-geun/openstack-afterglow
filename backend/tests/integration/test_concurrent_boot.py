"""N=CONCURRENT_VMS VM 동시 부팅 시 NFS share 동시 접근 안정성 검증.

실 인프라(Manila, Nova, SSH 도달 가능한 외부 네트워크) 필요 — self-hosted runner 전용.
로컬 단위 테스트 실행 시 자동 skip.

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 \
  AFTERGLOW_TEST_IMAGE_ID=<uuid> \
  AFTERGLOW_TEST_FLAVOR_SMALL=<uuid> \
  AFTERGLOW_TEST_FLAVOR_MEDIUM=<uuid> \
  AFTERGLOW_TEST_SSH_KEY=~/.ssh/afterglow-test \
  AFTERGLOW_TEST_CONCURRENT_VMS=5 \
  uv run pytest tests/integration/test_concurrent_boot.py -v -m slow
"""

import asyncio
import os

import pytest

from tests.integration.conftest import require_service
from tests.integration.ssh_helper import (
    verify_overlay_mount,
    wait_for_ssh,
)

pytestmark = pytest.mark.slow

CONCURRENT_VMS = int(os.getenv("AFTERGLOW_TEST_CONCURRENT_VMS", "3"))


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_vm_boot_nfs_stability(admin_client, integration_resources):
    """N=CONCURRENT_VMS VM을 동일 prebuilt library로 동시 생성 → 모두 ACTIVE +
    SSH로 OverlayFS 마운트 직접 확인 + 동일 lowerdir 콘텐츠 가시성 검증.
    """
    require_service("service_nova_enabled")
    require_service("service_manila_enabled")

    instance_ids: list[str] = []
    try:
        create_tasks = [
            asyncio.create_task(_create_vm(admin_client, i, integration_resources)) for i in range(CONCURRENT_VMS)
        ]
        results = await asyncio.gather(*create_tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"VM 생성 실패: {errors}"

        instance_ids = [r for r in results if isinstance(r, str)]
        assert len(instance_ids) == CONCURRENT_VMS

        # 모든 VM ACTIVE 대기 (최대 15분)
        await_tasks = [
            asyncio.create_task(_wait_for_active(admin_client, inst_id, timeout=900)) for inst_id in instance_ids
        ]
        statuses = await asyncio.gather(*await_tasks)
        for inst_id, status in zip(instance_ids, statuses, strict=True):
            assert status == "ACTIVE", f"VM {inst_id}가 ACTIVE에 도달하지 못함 (status={status})"

        # FIP 동시 할당
        fip_tasks = [asyncio.create_task(_assign_floating_ip(admin_client, inst_id)) for inst_id in instance_ids]
        hosts = await asyncio.gather(*fip_tasks)
        for inst_id, host in zip(instance_ids, hosts, strict=True):
            assert host, f"VM {inst_id} FIP 할당 실패"

        # SSH 가용 대기 (병렬)
        ssh_tasks = [
            asyncio.to_thread(
                wait_for_ssh,
                host,
                integration_resources.ssh_key_path,
                integration_resources.ssh_user,
                300,
            )
            for host in hosts
        ]
        ssh_ready = await asyncio.gather(*ssh_tasks)
        assert all(ssh_ready), f"일부 VM SSH 접속 불가: {list(zip(hosts, ssh_ready, strict=True))}"

        # OverlayFS 마운트 동시 검증 (각 VM에서 독립적으로 확인)
        await asyncio.sleep(30)  # union-overlay.service jitter backoff 흡수
        mount_tasks = [
            asyncio.to_thread(
                verify_overlay_mount,
                host,
                integration_resources.ssh_key_path,
                "/opt/layers/merged",
                integration_resources.ssh_user,
            )
            for host in hosts
        ]
        mounted = await asyncio.gather(*mount_tasks)
        assert all(mounted), f"일부 VM OverlayFS 미마운트: {list(zip(hosts, mounted, strict=True))}"

        # health 보고 추가 검증 (이중화)
        for inst_id in instance_ids:
            health = await _get_health(admin_client, inst_id)
            assert health.get("mount_ok") is True, f"VM {inst_id} mount_ok=False: {health}"
    finally:
        for inst_id in instance_ids:
            try:
                await admin_client.delete(f"/api/v1/instances/{inst_id}")
            except Exception:
                pass


async def _create_vm(client, idx: int, resources) -> str:
    resp = await client.post(
        "/api/v1/instances",
        json={
            "name": f"test-concurrent-{idx}",
            "image_id": resources.image_id,
            "flavor_id": resources.flavor_small,
            "libraries": resources.library_ids,
            "strategy": "prebuilt",
        },
    )
    assert resp.status_code == 201, f"VM {idx} 생성 실패: {resp.text}"
    return resp.json()["id"]


async def _wait_for_active(client, instance_id: str, timeout: int) -> str:
    for _ in range(timeout // 10):
        await asyncio.sleep(10)
        resp = await client.get(f"/api/v1/instances/{instance_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status in ("ACTIVE", "ERROR"):
                return status
    return "TIMEOUT"


async def _assign_floating_ip(client, instance_id: str) -> str | None:
    """FIP 자동 할당 후 IP 주소 반환."""
    resp = await client.get(f"/api/v1/instances/{instance_id}")
    if resp.status_code == 200:
        for ip in resp.json().get("ip_addresses", []):
            if ip.get("type") == "floating" and ip.get("addr"):
                return ip["addr"]
    resp = await client.post(f"/api/v1/instances/{instance_id}/floating-ip")
    if resp.status_code in (200, 201):
        return resp.json().get("floating_ip_address")
    return None


async def _get_health(client, instance_id: str) -> dict:
    resp = await client.get(f"/api/v1/instances/{instance_id}/health")
    if resp.status_code == 200:
        return resp.json()
    return {}
