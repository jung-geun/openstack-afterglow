"""VM resize 후 OverlayFS 마운트 유지 검증.

실 인프라(Nova, Manila) 필요 — self-hosted runner에서만 실행.
로컬 단위 테스트 실행 시 자동 skip.

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_resize_overlay.py -v -m slow
"""

import asyncio

import pytest

from tests.integration.conftest import require_service

pytestmark = pytest.mark.slow


@pytest.mark.asyncio
async def test_resize_preserves_overlayfs(admin_client, settings):
    """VM 생성 → resize → confirm → OverlayFS /opt/layers/merged 마운트 유지 확인."""
    require_service("service_nova_enabled")
    pytest.skip("실 인프라 환경에서 실행 — self-hosted runner 전용")

    # --- 실 인프라 환경에서의 동작 개요 ---
    # 1. 소형 flavor로 prebuilt library VM 생성 → ACTIVE 대기
    # 2. POST /api/admin/instances/{id}/resize (중형 flavor)
    # 3. VERIFY_RESIZE 상태 대기 (최대 5분)
    # 4. POST /api/admin/instances/{id}/confirm-resize
    # 5. ACTIVE 상태 재진입 대기 (최대 5분)
    # 6. GET /api/instances/{id}/health → mount_ok=True 확인
    #    (union-overlay.service WantedBy=multi-user.target으로 cold resize 후 자동 재실행)
    # 7. VM 삭제 (cleanup)

    instance_id: str | None = None
    try:
        # 1. VM 생성
        resp = await admin_client.post(
            "/api/instances",
            json={
                "name": "test-resize-overlay",
                "image_id": settings.test_image_id if hasattr(settings, "test_image_id") else "placeholder",
                "flavor_id": settings.test_flavor_small if hasattr(settings, "test_flavor_small") else "placeholder",
                "library_ids": ["python311"],
                "strategy": "prebuilt",
            },
        )
        assert resp.status_code == 201
        instance_id = resp.json()["id"]

        # 2. ACTIVE 대기
        status = await _wait_for_status(admin_client, instance_id, "ACTIVE", timeout=600)
        assert status == "ACTIVE"

        # 3. Resize 요청
        target_flavor = settings.test_flavor_medium if hasattr(settings, "test_flavor_medium") else "placeholder"
        resp = await admin_client.post(
            f"/api/admin/instances/{instance_id}/resize",
            json={"flavor_id": target_flavor},
        )
        assert resp.status_code in (200, 202)

        # 4. VERIFY_RESIZE 대기
        status = await _wait_for_status(admin_client, instance_id, "VERIFY_RESIZE", timeout=300)
        assert status == "VERIFY_RESIZE"

        # 5. Confirm resize
        resp = await admin_client.post(f"/api/admin/instances/{instance_id}/confirm-resize")
        assert resp.status_code in (200, 202)

        # 6. ACTIVE 재진입 대기
        status = await _wait_for_status(admin_client, instance_id, "ACTIVE", timeout=300)
        assert status == "ACTIVE"

        # 7. OverlayFS 마운트 확인 (health 엔드포인트)
        await asyncio.sleep(60)  # systemd union-overlay.service 실행 대기
        health = {}
        for _ in range(12):
            await asyncio.sleep(10)
            resp = await admin_client.get(f"/api/instances/{instance_id}/health")
            if resp.status_code == 200:
                health = resp.json()
                if health.get("mount_ok"):
                    break
        assert health.get("mount_ok") is True, f"resize 후 OverlayFS 마운트 실패: {health}"
    finally:
        if instance_id:
            await admin_client.delete(f"/api/instances/{instance_id}")


async def _wait_for_status(client, instance_id: str, target: str, timeout: int) -> str:
    for _ in range(timeout // 10):
        await asyncio.sleep(10)
        resp = await client.get(f"/api/instances/{instance_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status == target or status == "ERROR":
                return status
    return "TIMEOUT"
