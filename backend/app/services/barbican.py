"""Barbican (key-manager) 서비스 헬퍼.

§ PR2 — per-project KEK auto-provisioning.

owner project 의 Barbican 에서 k8s 용 KEK (key encryption key) 를 조회하거나,
없으면 신규 발급. cluster 별이 아니라 **project 별 공유 KEK** 패턴 — 같은 project
내 모든 cluster 가 같은 KEK 를 재사용 (lifecycle 단순, cluster delete 시 KEK 유지).

발급자는 § 28 의 manager user (`afterglow-cluster-mgr-<proj>`) — 같은 user 의
app credential 이 자동으로 read 권한을 가짐 (Barbican default policy: creator 접근).
"""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings

_logger = logging.getLogger(__name__)

KEK_NAME = "afterglow-k8s-kek"


async def ensure_project_kek(project_id: str) -> str:
    """프로젝트 owner Barbican 에서 k8s KEK 조회/발급. 반환: KEK UUID.

    동작:
    1. manager user 로 project-scoped Barbican 검색 (이름='afterglow-k8s-kek')
    2. 발견 + ACTIVE 면 그 UUID 반환 (idempotent)
    3. 없으면 secret order 발급 (aes/cbc/256, async). PENDING → ACTIVE 폴링.
    4. Secret ref URL 의 마지막 segment 가 UUID.
    """
    from app.services import keystone as _keystone

    user_id, password = await _keystone.ensure_cluster_manager_user(project_id)
    settings = get_settings()
    return await asyncio.to_thread(_ensure_project_kek_sync, project_id, password, settings)


def _ensure_project_kek_sync(project_id: str, password: str, settings) -> str:
    from app.services.keystone import _connect_as_manager

    conn = _connect_as_manager(project_id, password, settings)
    try:
        ep = conn.session.get_endpoint(service_type="key-manager")

        # 1. 기존 KEK 검색
        r = conn.session.get(f"{ep}/v1/secrets", params={"name": KEK_NAME})
        for s in r.json().get("secrets", []) or []:
            if s.get("status") == "ACTIVE":
                kek_id = s["secret_ref"].rsplit("/", 1)[-1]
                _logger.info("기존 KEK 재사용: project=%s kek=%s", project_id, kek_id)
                return kek_id

        # 2. 신규 order 발급
        _logger.info("신규 KEK order 발급: project=%s", project_id)
        order_resp = conn.session.post(
            f"{ep}/v1/orders",
            json={
                "type": "key",
                "meta": {
                    "name": KEK_NAME,
                    "algorithm": "aes",
                    "mode": "cbc",
                    "bit_length": 256,
                    "payload_content_type": "application/octet-stream",
                },
            },
        )
        order_resp.raise_for_status()
        order_ref = order_resp.json().get("order_ref")
        if not order_ref:
            raise RuntimeError(f"Barbican order 응답에 order_ref 없음: {order_resp.text[:200]}")

        # 3. order PENDING → ACTIVE 폴링 (최대 30초)
        import time

        for _ in range(30):
            o = conn.session.get(order_ref)
            o_body = o.json()
            status = o_body.get("status")
            if status == "ACTIVE":
                kek_id = o_body["secret_ref"].rsplit("/", 1)[-1]
                _logger.info("KEK 발급 완료: project=%s kek=%s", project_id, kek_id)
                return kek_id
            if status == "ERROR":
                raise RuntimeError(f"Barbican order 실패: {o_body.get('error_reason', 'unknown')}")
            time.sleep(1)
        raise RuntimeError("Barbican KEK order timeout (30s)")
    finally:
        conn.close()
