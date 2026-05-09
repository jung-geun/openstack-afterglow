"""Union v2 엔드투엔드 — Builder API → seal → fork → User mount 라이프사이클.

실 인프라(MariaDB, Manila 3-share — RW/RO/manifest) 가정. 자체 DB만 필요한 흐름은
manila 미활성 환경에서도 검증된다 (builder/user access 단계만 조건부 skip).

실행:
  cd backend
  AFTERGLOW_ALLOW_INSECURE=1 uv run pytest tests/integration/test_union_e2e.py -v -m slow
"""

from __future__ import annotations

import secrets

import pytest

from app.config import get_settings
from tests.integration.conftest import require_service

pytestmark = [pytest.mark.slow, pytest.mark.asyncio]


def _hash() -> str:
    return f"sha256:{secrets.token_hex(32)}"


async def _revoke_quietly(client, path: str) -> None:
    try:
        await client.delete(path)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_union_v2_lifecycle(admin_client, user_client):
    """Builder→seal→fork→template→user mount→unmount→cleanup 전 흐름.

    조립:
      1. (선택) builder access 부여
      2. RW 레이어 생성 (sealed=False)
      3. seal → sealed_id 획득
      4. ancestors 조회 — base-first
      5. fork → 새 RW 레이어 (sealed=False, parent=sealed_id)
      6. template 생성 — leaf_layer_id=sealed_id
      7. template 상세 조회 — resolved_stack 포함
      8. (선택) user access 부여
      9. user_client → record_mount
     10. layer 삭제 시도 → 409 (mount + template + fork 참조)
     11. unmount
     12. DELETE template → DELETE fork → DELETE sealed layer (cleanup 성공)
    """
    require_service("service_db_enabled")

    settings = get_settings()
    rw_share_id = getattr(settings, "union_layer_store_rw_share_id", "")
    ro_share_id = getattr(settings, "union_layer_store_ro_share_id", "")
    manila_enabled = bool(getattr(settings, "service_manila_enabled", False))

    builder_access_id: str | None = None
    user_access_id: str | None = None
    sealed_id: str | None = None
    fork_id: str | None = None
    template_name = f"e2e-test-{secrets.token_hex(4)}"
    template_version = 1
    template_created = False
    mount_id: int | None = None

    try:
        # 1. (선택) builder access — manila + RW share 설정 시에만
        if manila_enabled and rw_share_id:
            resp = await admin_client.post(
                "/api/union/builder/access",
                json={"cephx_user": f"e2e-builder-{secrets.token_hex(4)}", "access_level": "rw"},
            )
            assert resp.status_code == 201, f"builder access 실패: {resp.text}"
            builder_access_id = resp.json()["access_id"]

        # 2. RW 레이어 생성
        layer_hash = _hash()
        resp = await admin_client.post(
            "/api/union/layers",
            json={
                "name": f"e2e-base-{secrets.token_hex(4)}",
                "version": "1.0",
                "ubuntu_base": "ubuntu:22.04",
                "build_recipe": {"steps": []},
                "installed_packages": {},
                "content_hash": layer_hash,
                "size_bytes": 1024,
                "file_count": 10,
            },
        )
        assert resp.status_code == 201, f"레이어 생성 실패: {resp.text}"
        layer_id = resp.json()["id"]
        assert resp.json()["sealed"] is False

        # 3. seal
        resp = await admin_client.post(f"/api/union/layers/{layer_id}/seal")
        assert resp.status_code == 200, f"seal 실패: {resp.text}"
        body = resp.json()
        sealed_id = body["id"]
        assert body["sealed"] is True
        assert body.get("sealed_at"), "sealed_at 미설정"

        # 4. ancestors — base-first 순으로 self 한 항목
        resp = await admin_client.get(f"/api/union/layers/{sealed_id}/ancestors")
        assert resp.status_code == 200
        layers = resp.json().get("layers", [])
        assert len(layers) == 1, f"조상 체인 길이 예상=1 실제={len(layers)}"
        assert layers[0]["id"] == sealed_id

        # 5. fork — 새 RW 레이어
        fork_hash = _hash()
        resp = await admin_client.post(
            f"/api/union/layers/{sealed_id}/fork",
            json={"content_hash": fork_hash, "version": "1.1"},
        )
        assert resp.status_code == 201, f"fork 실패: {resp.text}"
        fork_body = resp.json()
        fork_id = fork_body["id"]
        assert fork_body["sealed"] is False
        assert fork_body["parent_id"] == sealed_id

        # 6. template 생성
        resp = await admin_client.post(
            "/api/union/templates",
            json={
                "name": template_name,
                "version": template_version,
                "ubuntu_base": "ubuntu:22.04",
                "leaf_layer_id": sealed_id,
            },
        )
        assert resp.status_code == 201, f"template 생성 실패: {resp.text}"
        template_created = True

        # 7. template 상세
        resp = await admin_client.get(f"/api/union/templates/{template_name}/{template_version}")
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["leaf_layer_id"] == sealed_id
        assert tmpl.get("resolved_stack") and len(tmpl["resolved_stack"]) >= 1

        # 8. (선택) user access
        if manila_enabled and ro_share_id:
            resp = await admin_client.post(
                "/api/union/user/access",
                json={"cephx_user": f"e2e-user-{secrets.token_hex(4)}", "access_level": "ro"},
            )
            assert resp.status_code == 201, f"user access 실패: {resp.text}"
            user_access_id = resp.json()["access_id"]

        # 9. user_client → record_mount
        resp = await user_client.post(
            "/api/union/mounts",
            json={"vm_hostname": "e2e-vm", "leaf_layer_id": sealed_id},
        )
        assert resp.status_code == 201, f"mount 등록 실패: {resp.text}"
        mount_body = resp.json()
        mount_id = mount_body["id"]
        assert mount_body["unmounted_at"] is None

        # 10. layer 삭제 시도 → 409 (mount + template + fork 참조)
        resp = await admin_client.delete(f"/api/union/layers/{sealed_id}")
        assert resp.status_code == 409, f"활성 참조 있는 layer 삭제가 거부되지 않음: {resp.status_code} {resp.text}"

        # 11. unmount
        resp = await user_client.post(f"/api/union/mounts/{mount_id}/unmount")
        assert resp.status_code == 200, f"unmount 실패: {resp.text}"
        assert resp.json().get("unmounted_at"), "unmounted_at 미설정"
        # 11-1. unmount 후에도 template/fork가 남아 있어 layer 삭제는 여전히 409
        resp = await admin_client.delete(f"/api/union/layers/{sealed_id}")
        assert resp.status_code == 409

        # 12. cleanup 순서: template → fork → sealed layer
        resp = await admin_client.delete(f"/api/union/templates/{template_name}/{template_version}")
        assert resp.status_code == 204, f"template 삭제 실패: {resp.text}"
        template_created = False

        resp = await admin_client.delete(f"/api/union/layers/{fork_id}")
        assert resp.status_code == 204, f"fork 삭제 실패: {resp.text}"
        fork_id = None

        resp = await admin_client.delete(f"/api/union/layers/{sealed_id}")
        assert resp.status_code == 204, f"sealed layer 삭제 실패: {resp.text}"
        sealed_id = None
    finally:
        # finally cleanup — best-effort, 잔여 리소스 회수
        if template_created:
            await _revoke_quietly(admin_client, f"/api/union/templates/{template_name}/{template_version}")
        if fork_id:
            await _revoke_quietly(admin_client, f"/api/union/layers/{fork_id}")
        if sealed_id:
            await _revoke_quietly(admin_client, f"/api/union/layers/{sealed_id}")
        if user_access_id:
            await _revoke_quietly(admin_client, f"/api/union/user/access/{user_access_id}")
        if builder_access_id:
            await _revoke_quietly(admin_client, f"/api/union/builder/access/{builder_access_id}")
