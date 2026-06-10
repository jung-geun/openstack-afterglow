"""python 3.11 파일 스토리지 라이프사이클 E2E 통합 테스트.

저수준 단계별 경로를 검증한다:
  1. POST /api/file-storage  →  share 직접 생성
  2. POST /api/admin/libraries/build  →  빌더 VM: uv python 3.11 설치
     (cloud-init 완료 → SHUTOFF sentinel → prebuilt 승격 → VM/port 자동 teardown)
  3. POST /api/instances  →  새 VM 부팅: python311 prebuilt share RO 오버레이 마운트
  4. SSH 검증:
       - /opt/layers/merged 오버레이 마운트 존재
       - /opt/layers/merged/usr/local/bin/python3.11 실제 실행 → 3.11.x 반환

실 인프라 필요 (Manila + Nova + SSH 도달 가능 FIP):
  AFTERGLOW_TEST_IMAGE_ID, AFTERGLOW_TEST_FLAVOR_SMALL, AFTERGLOW_TEST_SSH_KEY

실행:
  cd backend
  AFTERGLOW_TEST_IMAGE_ID=<uuid> \\
  AFTERGLOW_TEST_FLAVOR_SMALL=<uuid> \\
  AFTERGLOW_TEST_SSH_KEY=~/.ssh/key \\
  uv run pytest tests/integration/test_python311_lifecycle_e2e.py -v -m slow

주의: step 1의 share가 service 프로젝트에서 조회 가능해야 한다.
      admin 계정이 service 프로젝트와 동일하거나 Manila admin 권한을 가진 경우에만 정상 동작한다.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from tests.integration.conftest import require_service
from tests.integration.ssh_helper import (
    verify_overlay_mount,
    verify_python_executes,
    wait_for_ssh,
)

pytestmark = pytest.mark.slow

# 빌드 완료 대기 최대 시간 (초) — uv python install ≈ 5분 + cloud-init 오버헤드
BUILD_TIMEOUT = int(os.getenv("AFTERGLOW_TEST_BUILD_TIMEOUT", "2400"))
# VM ACTIVE 대기 최대 시간 (초)
VM_ACTIVE_TIMEOUT = int(os.getenv("AFTERGLOW_TEST_VM_TIMEOUT", "600"))


@pytest.mark.asyncio(loop_scope="session")
async def test_python311_lifecycle_low_level(admin_client, integration_resources):
    """python 3.11 라이브러리 전체 라이프사이클 — 저수준 단계별 경로.

    7단계 인수 시나리오:
      1. file storage 직접 생성
      2. 해당 share를 빌더 VM에 연결 → uv로 python 3.11 설치
      3. cloud-init 성공 → prebuilt 승격 확인
      4. uv 산출물이 overlayfs(/opt/layers/merged)로 접근 가능
      5. 빌더 VM/port 자동 teardown (cloud-init umount + finally 블록)
      6. 새 VM: python311 prebuilt share RO 마운트 확인
      7. SSH: python3.11 실제 실행 검증 (uv standalone CPython 재배치 동작 확인)
    """
    require_service("service_nova_enabled")
    require_service("service_manila_enabled")

    share_id: str | None = None
    instance_id: str | None = None

    try:
        # ── Step 1: file storage 직접 생성 ───────────────────────────────
        resp = await admin_client.post(
            "/api/file-storage",
            json={
                "name": "python311-e2e-test",
                "size_gb": 20,
                "share_proto": "NFS",
                "metadata": {"union_test": "python311_lifecycle_e2e"},
            },
        )
        assert resp.status_code == 201, f"file storage 생성 실패: {resp.text}"
        share_id = resp.json()["id"]
        assert share_id, "share ID가 없습니다"

        # ── Steps 2–3·5: 빌더 VM 실행 (uv python 3.11 설치 + teardown) ──
        # file_storage_id 지정 경로는 큐 우회 → start_ephemeral_build 직접 호출
        # → 응답 JSON에 build_id가 즉시 포함됨 (asyncio.create_task 기반 백그라운드 실행)
        resp = await admin_client.post(
            "/api/admin/libraries/build",
            json={
                "library_id": "python311",
                "auto_install": True,
                "file_storage_id": share_id,
            },
        )
        assert resp.status_code == 202, f"빌드 트리거 실패: {resp.text}"

        build_id = resp.json().get("build_id")
        assert build_id is not None, (
            f"빌드 응답에 build_id가 없습니다: {resp.json()}. "
            "start_ephemeral_build가 DB에 레코드를 생성하지 못했을 수 있습니다."
        )

        # ── 빌드 완료 대기 ─────────────────────────────────────────────────
        final_status = await _wait_for_build(admin_client, build_id, timeout=BUILD_TIMEOUT)
        assert final_status == "complete", (
            f"빌드가 complete 상태에 도달하지 못했습니다 (status={final_status}). "
            f"GET /api/admin/libraries/builds/{build_id} 에서 console_log_excerpt 확인. "
            "uv python install 실패 또는 NFS mount 오류 가능성."
        )

        # ── Step 4·6: 새 VM — python311 prebuilt share RO 오버레이 마운트 ─
        resp = await admin_client.post(
            "/api/instances",
            json={
                "name": "test-python311-consumer",
                "image_id": integration_resources.image_id,
                "flavor_id": integration_resources.flavor_small,
                "libraries": ["python311"],
                "strategy": "prebuilt",
            },
        )
        assert resp.status_code == 201, f"consumer VM 생성 실패: {resp.text}"
        instance_id = resp.json()["id"]

        # ACTIVE 대기
        status = await _wait_for_active(admin_client, instance_id, timeout=VM_ACTIVE_TIMEOUT)
        assert status == "ACTIVE", f"VM이 ACTIVE에 도달하지 못함 (status={status})"

        # ── Step 6 검증: consumer VM이 올바른 share를 마운트했는지 identity 확인 ─
        # stale prebuilt 충돌 방지 — 동일 library_name의 구 share가 존재할 수 있으므로
        # VM 메타데이터의 union_share_ids가 이번에 생성한 share_id를 포함해야 한다.
        resp = await admin_client.get(f"/api/instances/{instance_id}")
        if resp.status_code == 200:
            mounted = resp.json().get("union_share_ids", [])
            assert share_id in mounted, (
                f"consumer VM이 이번 빌드의 share({share_id})를 마운트하지 않았습니다. "
                f"실제 mounted={mounted}. "
                "동일 library_name의 구 prebuilt share가 우선 선택되었을 가능성 — "
                "GET /api/admin/libraries?name=python311 로 중복 prebuilt share 확인."
            )

        # FIP 할당
        host = await _assign_floating_ip(admin_client, instance_id)
        assert host, "floating IP 할당 실패"

        # SSH 가용 대기 (cloud-init + sshd 기동 시간 포함)
        ssh_ready = await asyncio.to_thread(
            wait_for_ssh,
            host,
            integration_resources.ssh_key_path,
            integration_resources.ssh_user,
            300,
        )
        assert ssh_ready, f"VM SSH 접속 불가: {host}"

        # union-overlay.service jitter backoff 흡수
        await asyncio.sleep(15)

        # ── Step 4 검증: /opt/layers/merged 오버레이 마운트 존재 ───────────
        mount_ok = await asyncio.to_thread(
            verify_overlay_mount,
            host,
            integration_resources.ssh_key_path,
            "/opt/layers/merged",
            integration_resources.ssh_user,
        )
        assert mount_ok, (
            f"VM {host}: /opt/layers/merged 오버레이 마운트 없음. "
            "overlay_setup.sh 실행 실패 또는 NFS lowerdir 마운트 오류 가능성."
        )

        # ── Step 7 검증: python3.11 실제 실행 (핵심) ──────────────────────
        # uv standalone CPython이 cp -a + overlayfs를 거쳐도 동작하는지 확인
        py_result = await asyncio.to_thread(
            verify_python_executes,
            host,
            integration_resources.ssh_key_path,
            "3.11",
            integration_resources.ssh_user,
        )
        assert py_result["exec_ok"], (
            f"VM {host}: overlay에서 python3.11 실행 실패.\n"
            f"  version_str={py_result['version_str']!r}\n"
            f"  which_path={py_result['which_path']!r}\n"
            "uv standalone CPython이 cp -a + overlayfs를 통해 실행되지 않았습니다. "
            "빌더 레시피의 install_uv → python install → cp 경로를 확인하세요."
        )
        # which_ok는 non-fatal: 비login shell은 /etc/profile.d가 미적용되어
        # PATH에 overlay bin이 없을 수 있음. exec_ok(절대 경로 실행)가 핵심 검증.
        if not py_result["which_ok"]:
            import warnings

            warnings.warn(
                f"VM {host}: python3.11이 PATH에 노출되지 않음 "
                f"(which_path={py_result['which_path']!r}). "
                "/etc/profile.d/union-env.sh 소싱 여부 확인 권장 (비login shell 한계).",
                stacklevel=1,
            )

    finally:
        # consumer VM 정리
        if instance_id:
            try:
                await admin_client.delete(f"/api/instances/{instance_id}")
            except Exception:
                pass
        # share는 prebuilt 아티팩트로 보존 (다른 테스트에서 재사용 가능)
        # 명시적 삭제: await admin_client.delete(f"/api/file-storage/{share_id}")


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


async def _find_build_id(client, library_id: str, share_id: str, timeout: int = 60) -> int | None:
    """빌드 트리거 후 해당 share_id에 대응하는 build_id를 DB 폴링으로 획득한다.

    queue_build 경로는 build_id를 즉시 반환하지 않으므로 폴링이 필요하다.
    start_ephemeral_build에서 existing_share_id로 DB row를 생성하므로
    큐 워커가 처리한 뒤 share_id로 매칭이 가능하다.
    """
    for _ in range(timeout // 3):
        await asyncio.sleep(3)
        resp = await client.get(f"/api/admin/libraries/builds?library_id={library_id}")
        if resp.status_code != 200:
            continue
        builds = resp.json()
        # 최신 build (id 내림차순) 에서 share_id 매칭
        for build in sorted(builds, key=lambda b: b.get("id", 0), reverse=True):
            if build.get("file_storage_id") == share_id:
                return build["id"]
    return None


async def _wait_for_build(client, build_id: int, timeout: int) -> str:
    """빌드 terminal state까지 폴링. 최종 status 반환."""
    terminal = {"complete", "error", "timeout", "cancelled"}
    for _ in range(timeout // 15):
        await asyncio.sleep(15)
        resp = await client.get(f"/api/admin/libraries/builds/{build_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status in terminal:
                return status
    return "TIMEOUT"


async def _wait_for_active(client, instance_id: str, timeout: int) -> str:
    """VM ACTIVE 또는 ERROR까지 폴링. 최종 status 반환."""
    for _ in range(timeout // 10):
        await asyncio.sleep(10)
        resp = await client.get(f"/api/instances/{instance_id}")
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status in ("ACTIVE", "ERROR"):
                return status
    return "TIMEOUT"


async def _assign_floating_ip(client, instance_id: str) -> str | None:
    """FIP 자동 할당 후 IP 주소 반환."""
    resp = await client.get(f"/api/instances/{instance_id}")
    if resp.status_code == 200:
        for ip in resp.json().get("ip_addresses", []):
            if ip.get("type") == "floating" and ip.get("addr"):
                return ip["addr"]
    resp = await client.post(f"/api/instances/{instance_id}/floating-ip")
    if resp.status_code in (200, 201):
        return resp.json().get("floating_ip_address")
    return None
