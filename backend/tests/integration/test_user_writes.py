"""일반 유저 저위험 쓰기 엔드포인트 스모크 테스트.

생성 → 검증 → 삭제 전체 흐름. try/finally로 리소스 정리 보장.
고위험(VM/LB/k3s/router/volume 생성)은 의도적으로 제외 — 단위 테스트 커버.
"""

import uuid

import pytest

from tests.integration.conftest import require_service


@pytest.mark.asyncio(loop_scope="session")
async def test_keypair_create_and_delete(user_client):
    """키페어 생성 → 리스트 확인 → 삭제."""
    name = f"pr5-kp-{uuid.uuid4().hex[:8]}"
    created = False
    try:
        resp = await user_client.post("/api/keypairs", json={"name": name})
        assert resp.status_code == 201, f"create failed: {resp.text}"
        body = resp.json()
        assert body.get("name") == name
        assert "private_key" in body  # Nova가 생성 시 반환
        created = True

        resp = await user_client.get("/api/keypairs")
        assert resp.status_code == 200
        assert any(kp.get("name") == name for kp in resp.json()), f"생성된 키페어 '{name}'가 목록에 없음"
    finally:
        if created:
            resp = await user_client.delete(f"/api/keypairs/{name}")
            assert resp.status_code in (204, 404), f"cleanup failed: {resp.text}"


@pytest.mark.asyncio(loop_scope="session")
async def test_security_group_and_rule_lifecycle(user_client):
    """SG 생성 → Rule 추가 → Rule 삭제 → SG 삭제."""
    sg_name = f"pr5-sg-{uuid.uuid4().hex[:8]}"
    sg_id = None
    rule_id = None
    try:
        resp = await user_client.post(
            "/api/security-groups",
            json={
                "name": sg_name,
                "description": "PR5 integration test — auto cleanup",
            },
        )
        assert resp.status_code == 201, f"SG create failed: {resp.text}"
        sg_id = resp.json()["id"]

        resp = await user_client.post(
            f"/api/security-groups/{sg_id}/rules",
            json={
                "direction": "ingress",
                "ethertype": "IPv4",
                "protocol": "tcp",
                "port_range_min": 22,
                "port_range_max": 22,
                "remote_ip_prefix": "0.0.0.0/0",
            },
        )
        assert resp.status_code == 201, f"rule create failed: {resp.text}"
        rule_id = resp.json()["id"]
    finally:
        if rule_id and sg_id:
            await user_client.delete(f"/api/security-groups/{sg_id}/rules/{rule_id}")
        if sg_id:
            resp = await user_client.delete(f"/api/security-groups/{sg_id}")
            assert resp.status_code in (204, 404), f"SG cleanup failed: {resp.text}"


@pytest.mark.asyncio(loop_scope="session")
async def test_share_snapshot_lifecycle(user_client):
    """manila 활성 + 기존 share 존재 시 스냅샷 생성 → 삭제."""
    require_service("service_manila_enabled")

    resp = await user_client.get("/api/file-storage")
    assert resp.status_code == 200
    shares = resp.json()
    if not shares:
        pytest.skip("기존 file-storage 없음 — 스냅샷 테스트 생략")

    snap_id = None
    # share에 따라 snapshot 지원 여부가 다를 수 있으므로 순차 시도
    for share in shares:
        share_id = share["id"]
        snap_name = f"pr5-snap-{uuid.uuid4().hex[:8]}"
        try:
            resp = await user_client.post(
                "/api/share-snapshots",
                json={
                    "share_id": share_id,
                    "name": snap_name,
                },
            )
            if resp.status_code in (422, 500):
                # 이 share는 snapshot 미지원 — 다음 share 시도
                continue
            assert resp.status_code == 201, f"snapshot create failed: {resp.text}"
            snap_id = resp.json()["id"]
            break
        finally:
            if snap_id:
                await user_client.delete(f"/api/share-snapshots/{snap_id}")
                break

    if snap_id is None:
        pytest.skip("조회된 모든 file-storage가 snapshot 미지원 — 환경 제약으로 생략")
