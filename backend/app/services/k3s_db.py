"""k3s 클러스터 DB CRUD.

DB가 초기화되어 있으면 MariaDB를 사용하고,
미설정 시 기존 Redis 방식(k3s_cluster.py)으로 폴백.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete

from app.database import is_db_available, get_session_factory
from app.models.db import K3sCluster, K3sAgentVM
from app.services.k3s_crypto import encrypt_kubeconfig, decrypt_kubeconfig

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _cluster_to_dict(cluster: K3sCluster) -> dict:
    """ORM 모델 → API 응답 호환 dict 변환."""
    agent_vms = cluster.agent_vms or []
    return {
        "id": cluster.id,
        "project_id": cluster.project_id,
        "name": cluster.name,
        "status": cluster.status,
        "status_reason": cluster.status_reason,
        "server_vm_id": cluster.server_vm_id,
        "agent_vm_ids": [v.vm_id for v in agent_vms],
        "agent_count": cluster.agent_count,
        "server_flavor_id": cluster.server_flavor_id,
        "agent_flavor_id": cluster.agent_flavor_id,
        "network_id": cluster.network_id,
        "security_group_id": cluster.security_group_id,
        "server_ip": cluster.server_ip,
        "api_address": cluster.api_address,
        "key_name": cluster.key_name,
        "ssh_public_key": cluster.ssh_public_key,
        "k3s_version": cluster.k3s_version,
        "created_by_user_id": cluster.created_by_user_id,
        "created_by_username": cluster.created_by_username,
        "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
        "updated_at": cluster.updated_at.isoformat() if cluster.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Cluster CRUD
# ---------------------------------------------------------------------------

async def create_cluster_record(project_id: str, cluster_id: str, data: dict) -> None:
    """클러스터 생성. DB 미설정 시 Redis 폴백."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.create_cluster_record(project_id, cluster_id, data)

    factory = get_session_factory()
    async with factory() as session:
        cluster = K3sCluster(
            id=cluster_id,
            project_id=project_id,
            name=data.get("name", ""),
            status=data.get("status", "CREATING"),
            status_reason=data.get("status_reason") or None,
            server_vm_id=data.get("server_vm_id") or None,
            server_flavor_id=data.get("server_flavor_id") or None,
            agent_flavor_id=data.get("agent_flavor_id") or None,
            network_id=data.get("network_id") or None,
            security_group_id=data.get("security_group_id") or None,
            server_ip=data.get("server_ip") or None,
            api_address=data.get("api_address") or None,
            k3s_version=data.get("k3s_version") or None,
            key_name=data.get("key_name") or None,
            ssh_public_key=data.get("ssh_public_key") or None,
            agent_count=int(data.get("agent_count") or 0),
            created_by_user_id=data.get("created_by_user_id") or None,
            created_by_username=data.get("created_by_username") or None,
        )
        session.add(cluster)
        await session.commit()


async def get_cluster(project_id: str, cluster_id: str) -> Optional[dict]:
    """단일 클러스터 조회. 없으면 None."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.get_cluster(project_id, cluster_id)

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(K3sCluster)
            .where(K3sCluster.id == cluster_id, K3sCluster.project_id == project_id)
        )
        result = await session.execute(stmt)
        cluster = result.scalar_one_or_none()
        if cluster is None:
            return None
        # agent_vms lazy load
        await session.refresh(cluster, ["agent_vms"])
        return _cluster_to_dict(cluster)


async def list_clusters(project_id: str) -> list[dict]:
    """프로젝트의 클러스터 목록 (최신순)."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.list_clusters(project_id)

    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(K3sCluster)
            .where(K3sCluster.project_id == project_id)
            .order_by(K3sCluster.created_at.desc())
        )
        result = await session.execute(stmt)
        clusters = result.scalars().all()
        out = []
        for c in clusters:
            await session.refresh(c, ["agent_vms"])
            out.append(_cluster_to_dict(c))
        return out


async def list_all_clusters() -> list[dict]:
    """전체 프로젝트의 클러스터 목록 (관리자용)."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.list_all_clusters()

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sCluster).order_by(K3sCluster.created_at.desc())
        result = await session.execute(stmt)
        clusters = result.scalars().all()
        out = []
        for c in clusters:
            await session.refresh(c, ["agent_vms"])
            d = _cluster_to_dict(c)
            d["project_id"] = c.project_id
            out.append(d)
        return out


async def update_cluster_status(
    project_id: str,
    cluster_id: str,
    status: str,
    status_reason: Optional[str] = None,
    **extra_fields,
) -> None:
    """상태 업데이트 + 추가 필드 (server_ip, api_address, node_token 등)."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.update_cluster_status(
            project_id, cluster_id, status, status_reason, **extra_fields
        )

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sCluster).where(
            K3sCluster.id == cluster_id, K3sCluster.project_id == project_id
        )
        result = await session.execute(stmt)
        cluster = result.scalar_one_or_none()
        if cluster is None:
            _logger.warning("update_cluster_status: cluster %s not found", cluster_id)
            return

        cluster.status = status
        cluster.updated_at = datetime.now(timezone.utc)
        if status_reason is not None:
            cluster.status_reason = status_reason

        # 허용된 컬럼 매핑
        _column_map = {
            "server_ip", "api_address", "k3s_version", "node_token",
            "server_vm_id", "network_id", "security_group_id",
            "server_flavor_id", "agent_flavor_id", "key_name", "ssh_public_key",
        }
        for k, v in extra_fields.items():
            if k in _column_map:
                setattr(cluster, k, v if v else None)
            # agent_vm_ids는 add_agent_vms()로 별도 처리

        await session.commit()


async def delete_cluster_record(project_id: str, cluster_id: str) -> None:
    """클러스터 삭제 (agent_vms CASCADE 삭제 포함)."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.delete_cluster_record(project_id, cluster_id)

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(K3sCluster).where(
                K3sCluster.id == cluster_id, K3sCluster.project_id == project_id
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# 에이전트 VM
# ---------------------------------------------------------------------------

async def add_agent_vms(cluster_id: str, vm_entries: list[dict]) -> None:
    """에이전트 VM 레코드 추가. vm_entries: [{"vm_id": ..., "name": ...}, ...]"""
    if not is_db_available():
        # Redis 폴백: agent_vm_ids를 기존 방식으로 업데이트
        # cluster의 project_id를 가져와야 하므로 Redis에서 직접 처리
        return

    factory = get_session_factory()
    async with factory() as session:
        for entry in vm_entries:
            vm = K3sAgentVM(
                cluster_id=cluster_id,
                vm_id=entry["vm_id"],
                name=entry.get("name"),
                status="CREATING",
            )
            session.add(vm)
        await session.commit()


async def update_agent_vm_status(cluster_id: str, vm_id: str, status: str) -> None:
    """에이전트 VM 상태 업데이트."""
    if not is_db_available():
        return

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sAgentVM).where(
            K3sAgentVM.cluster_id == cluster_id,
            K3sAgentVM.vm_id == vm_id,
        )
        result = await session.execute(stmt)
        vm = result.scalar_one_or_none()
        if vm:
            vm.status = status
            await session.commit()


# ---------------------------------------------------------------------------
# Kubeconfig
# ---------------------------------------------------------------------------

async def store_kubeconfig(project_id: str, cluster_id: str, kubeconfig_yaml: str) -> None:
    """kubeconfig를 AES-256-GCM 암호화하여 저장."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.store_kubeconfig(project_id, cluster_id, kubeconfig_yaml)

    encrypted = encrypt_kubeconfig(kubeconfig_yaml)
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sCluster).where(
            K3sCluster.id == cluster_id, K3sCluster.project_id == project_id
        )
        result = await session.execute(stmt)
        cluster = result.scalar_one_or_none()
        if cluster:
            cluster.kubeconfig_encrypted = encrypted
            cluster.updated_at = datetime.now(timezone.utc)
            await session.commit()


async def get_kubeconfig(project_id: str, cluster_id: str) -> Optional[str]:
    """암호화된 kubeconfig를 복호화하여 반환. 없으면 None."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.get_kubeconfig(project_id, cluster_id)

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sCluster.kubeconfig_encrypted).where(
            K3sCluster.id == cluster_id, K3sCluster.project_id == project_id
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if not row:
            return None
        return decrypt_kubeconfig(row)


# ---------------------------------------------------------------------------
# 콜백 토큰 — Redis 유지 (TTL 일회성, DB 불필요)
# ---------------------------------------------------------------------------

async def create_callback_token(project_id: str, cluster_id: str) -> str:
    from app.services import k3s_cluster as _redis
    return await _redis.create_callback_token(project_id, cluster_id)


async def consume_callback_token(token: str) -> Optional[dict]:
    from app.services import k3s_cluster as _redis
    return await _redis.consume_callback_token(token)


# ---------------------------------------------------------------------------
# 스테일 클러스터 정리
# ---------------------------------------------------------------------------

async def check_stale_clusters(timeout_minutes: int = 30) -> None:
    """CREATING/PROVISIONING 상태에서 timeout_minutes 초과 시 ERROR로 변경."""
    if not is_db_available():
        from app.services import k3s_cluster as _redis
        return await _redis.check_stale_clusters(timeout_minutes)

    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(K3sCluster).where(
            K3sCluster.status.in_(["CREATING", "PROVISIONING"]),
            K3sCluster.created_at < cutoff,
        )
        result = await session.execute(stmt)
        stale = result.scalars().all()
        for cluster in stale:
            cluster.status = "ERROR"
            cluster.status_reason = "콜백 타임아웃: 서버 VM이 k3s 설치 후 응답하지 않았습니다."
            cluster.updated_at = datetime.now(timezone.utc)
            _logger.warning("k3s cluster %s marked as ERROR (stale)", cluster.id)
        if stale:
            await session.commit()
