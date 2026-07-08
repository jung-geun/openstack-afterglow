"""VM resize 후 OverlayFS 마운트 유지 검증.

실 인프라(Nova, Manila, SSH 도달 가능한 외부 네트워크) 필요 — self-hosted runner 전용.
로컬 단위 테스트 실행 시 자동 skip.

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 \
  AFTERGLOW_TEST_IMAGE_ID=<uuid> \
  AFTERGLOW_TEST_FLAVOR_SMALL=<uuid> \
  AFTERGLOW_TEST_FLAVOR_MEDIUM=<uuid> \
  AFTERGLOW_TEST_SSH_KEY=~/.ssh/afterglow-test \
  uv run pytest tests/integration/test_resize_overlay.py -v -m slow
"""

import asyncio

import pytest

from tests.integration.conftest import require_service
from tests.integration.ssh_helper import (
    verify_overlay_mount,
    wait_for_ssh,
)

pytestmark = pytest.mark.slow


@pytest.mark.asyncio
async def test_resize_preserves_overlayfs(admin_client, integration_resources):
    """VM 생성 → resize → confirm → OverlayFS /opt/layers/merged 마운트 유지 확인.

    health endpoint(`mount_ok`)와 SSH 직접 검증을 모두 사용해 회귀 신호를 이중화한다.
    """
    require_service("service_nova_enabled")

    instance_id: str | None = None
    try:
        # 1. VM 생성
        resp = await admin_client.post(
            "/api/v1/instances",
            json={
                "name": "test-resize-overlay",
                "image_id": integration_resources.image_id,
                "flavor_id": integration_resources.flavor_small,
                "libraries": integration_resources.library_ids,
                "strategy": "prebuilt",
            },
        )
        assert resp.status_code == 201, f"VM 생성 실패: {resp.text}"
        instance_id = resp.json()["id"]

        # 2. ACTIVE 대기
        status = await _wait_for_status(admin_client, instance_id, "ACTIVE", timeout=600)
        assert status == "ACTIVE", f"VM이 ACTIVE에 도달하지 못함: {status}"

        # 3. Floating IP 할당
        host = await _assign_floating_ip(admin_client, instance_id)
        assert host, "Floating IP 할당 실패"

        # 4. SSH 가용 시점 대기 (cloud-init + sshd 기동)
        ssh_ready = await asyncio.to_thread(
            wait_for_ssh,
            host,
            integration_resources.ssh_key_path,
            integration_resources.ssh_user,
            300,
        )
        assert ssh_ready, f"{host} SSH 접속 불가"

        # 5. union-overlay.service 가 마운트할 시간 (jitter backoff 포함 수십초)
        for _ in range(24):
            if await asyncio.to_thread(
                verify_overlay_mount,
                host,
                integration_resources.ssh_key_path,
                "/opt/layers/merged",
                integration_resources.ssh_user,
            ):
                break
            await asyncio.sleep(5)
        else:
            pytest.fail("초기 부팅 후 OverlayFS 마운트 확인 실패")

        # 6. Resize 요청
        resp = await admin_client.post(
            f"/api/v1/admin/instances/{instance_id}/resize",
            json={"flavor_id": integration_resources.flavor_medium},
        )
        assert resp.status_code in (200, 202), f"resize 실패: {resp.text}"

        # 7. VERIFY_RESIZE 대기
        status = await _wait_for_status(admin_client, instance_id, "VERIFY_RESIZE", timeout=600)
        assert status == "VERIFY_RESIZE"

        # 8. Confirm resize
        resp = await admin_client.post(f"/api/v1/admin/instances/{instance_id}/confirm-resize")
        assert resp.status_code in (200, 202)

        # 9. ACTIVE 재진입 대기
        status = await _wait_for_status(admin_client, instance_id, "ACTIVE", timeout=600)
        assert status == "ACTIVE"

        # 10. SSH 재가용 대기 (resize는 cold restart 동반)
        ssh_ready = await asyncio.to_thread(
            wait_for_ssh,
            host,
            integration_resources.ssh_key_path,
            integration_resources.ssh_user,
            300,
        )
        assert ssh_ready, f"resize 후 {host} SSH 재접속 불가"

        # 11. SSH로 OverlayFS 재마운트/유지 확인
        for _ in range(24):
            if await asyncio.to_thread(
                verify_overlay_mount,
                host,
                integration_resources.ssh_key_path,
                "/opt/layers/merged",
                integration_resources.ssh_user,
            ):
                break
            await asyncio.sleep(5)
        else:
            pytest.fail("resize 후 OverlayFS 재마운트 실패")

        # 12. health endpoint 추가 검증
        health = {}
        for _ in range(12):
            await asyncio.sleep(10)
            resp = await admin_client.get(f"/api/v1/instances/{instance_id}/health")
            if resp.status_code == 200:
                health = resp.json()
                if health.get("mount_ok"):
                    break
        assert health.get("mount_ok") is True, f"resize 후 health.mount_ok=False: {health}"
    finally:
        if instance_id:
            await admin_client.delete(f"/api/v1/instances/{instance_id}")


async def _wait_for_status(client, instance_id: str, target: str, timeout: int) -> str:
    for _ in range(timeout // 10):
        await asyncio.sleep(10)
        resp = await client.get(f"/api/v1/instances/{instance_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status == target or status == "ERROR":
                return status
    return "TIMEOUT"


async def _assign_floating_ip(client, instance_id: str) -> str | None:
    """FIP 자동 생성+연결 후 IP 주소 반환. 이미 FIP가 있으면 그것을 반환."""
    # 기존 floating IP 확인
    resp = await client.get(f"/api/v1/instances/{instance_id}")
    if resp.status_code == 200:
        for ip in resp.json().get("ip_addresses", []):
            if ip.get("type") == "floating" and ip.get("addr"):
                return ip["addr"]

    # 신규 FIP 생성+연결
    resp = await client.post(f"/api/v1/instances/{instance_id}/floating-ip")
    if resp.status_code in (200, 201):
        return resp.json().get("floating_ip_address")
    return None
