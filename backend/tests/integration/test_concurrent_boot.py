"""N=5 VM 동시 부팅 시 NFS share 동시 접근 안정성 검증.

실 인프라(Manila, Nova) 필요 — self-hosted runner에서만 실행.
로컬 단위 테스트 실행 시 자동 skip.

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_concurrent_boot.py -v -m slow
"""

import asyncio
import os

import pytest

from tests.integration.conftest import require_service

pytestmark = pytest.mark.slow

CONCURRENT_VMS = int(os.getenv("AFTERGLOW_TEST_CONCURRENT_VMS", "3"))


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_vm_boot_nfs_stability(admin_client, settings):
    """N=CONCURRENT_VMS VM을 동일 prebuilt library로 동시 생성 → 모두 ACTIVE + health 보고 도달."""
    require_service("service_nova_enabled")
    require_service("service_manila_enabled")

    instance_ids: list[str] = []
    try:
        create_tasks = [asyncio.create_task(_create_vm(admin_client, i)) for i in range(CONCURRENT_VMS)]
        results = await asyncio.gather(*create_tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"VM 생성 실패: {errors}"

        instance_ids = [r for r in results if isinstance(r, str)]
        assert len(instance_ids) == CONCURRENT_VMS

        # 모든 VM ACTIVE 대기 (최대 15분)
        for inst_id in instance_ids:
            status = await _wait_for_active(admin_client, inst_id, timeout=900)
            assert status == "ACTIVE", f"VM {inst_id}가 ACTIVE에 도달하지 못함 (status={status})"

        # health 보고 확인
        for inst_id in instance_ids:
            health = await _get_health(admin_client, inst_id)
            assert health.get("mount_ok") is True, f"VM {inst_id} mount_ok=False: {health}"
    finally:
        for inst_id in instance_ids:
            await admin_client.delete(f"/api/instances/{inst_id}")


async def _create_vm(client, idx: int) -> str:
    resp = await client.post(
        "/api/instances",
        json={
            "name": f"test-concurrent-{idx}",
            "image_id": "placeholder",
            "flavor_id": "placeholder",
            "library_ids": ["python311"],
            "strategy": "prebuilt",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _wait_for_active(client, instance_id: str, timeout: int) -> str:
    for _ in range(timeout // 10):
        await asyncio.sleep(10)
        resp = await client.get(f"/api/instances/{instance_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status in ("ACTIVE", "ERROR"):
                return status
    return "TIMEOUT"


async def _get_health(client, instance_id: str) -> dict:
    resp = await client.get(f"/api/instances/{instance_id}/health")
    if resp.status_code == 200:
        return resp.json()
    return {}
