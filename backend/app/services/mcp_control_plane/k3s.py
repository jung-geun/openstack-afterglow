"""Project-owned, redacted K3s cluster read adapters for consumer MCP."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database import get_session_factory, is_db_available
from app.models.db import K3sCluster


class McpK3sError(ValueError):
    """K3s cluster data is unavailable or current-project scope cannot be proven."""


def _safe_cluster(cluster: Any, *, project_id: str) -> dict[str, Any]:
    owner_project_id = getattr(cluster, "project_id", None)
    if isinstance(cluster, dict):
        owner_project_id = cluster.get("project_id")
    if owner_project_id != project_id:
        raise McpK3sError("K3s cluster ownership cannot be proven")

    cid = getattr(cluster, "id", None) if not isinstance(cluster, dict) else cluster.get("id")
    if not cid:
        raise McpK3sError("K3s cluster id is missing")

    name = getattr(cluster, "name", "") if not isinstance(cluster, dict) else cluster.get("name", "")
    status = getattr(cluster, "status", "") if not isinstance(cluster, dict) else cluster.get("status", "")
    agent_count = getattr(cluster, "agent_count", 0) if not isinstance(cluster, dict) else cluster.get("agent_count", 0)
    k3s_version = getattr(cluster, "k3s_version", None) if not isinstance(cluster, dict) else cluster.get("k3s_version")
    created_at = getattr(cluster, "created_at", None) if not isinstance(cluster, dict) else cluster.get("created_at")
    updated_at = getattr(cluster, "updated_at", None) if not isinstance(cluster, dict) else cluster.get("updated_at")
    master_count = (
        getattr(cluster, "master_count", 1) if not isinstance(cluster, dict) else cluster.get("master_count", 1)
    )
    stampede_enabled = (
        getattr(cluster, "stampede_enabled", False)
        if not isinstance(cluster, dict)
        else cluster.get("stampede_enabled", False)
    )
    occm_enabled = (
        getattr(cluster, "occm_enabled", False) if not isinstance(cluster, dict) else cluster.get("occm_enabled", False)
    )

    return {
        "id": str(cid),
        "name": str(name or ""),
        "status": str(status or ""),
        "agent_count": int(agent_count or 0),
        "k3s_version": str(k3s_version) if k3s_version else None,
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else (str(created_at) if created_at else None),
        "updated_at": updated_at.isoformat()
        if hasattr(updated_at, "isoformat")
        else (str(updated_at) if updated_at else None),
        "master_count": int(master_count or 1),
        "stampede_enabled": bool(stampede_enabled),
        "occm_enabled": bool(occm_enabled),
    }


async def list_project_k3s_clusters(project_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return exact-project K3s clusters with bounded non-sensitive fields only."""
    if not is_db_available():
        raise McpK3sError("K3s database is unavailable")

    factory = get_session_factory()
    try:
        async with factory() as session:
            stmt = (
                select(K3sCluster)
                .where(K3sCluster.project_id == project_id, K3sCluster.deleted_at.is_(None))
                .order_by(K3sCluster.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            clusters = result.scalars().all()
            return [_safe_cluster(c, project_id=project_id) for c in clusters]
    except Exception as exc:
        if isinstance(exc, McpK3sError):
            raise
        raise McpK3sError("K3s cluster list query failed") from exc


async def get_project_k3s_cluster(project_id: str, cluster_id: str) -> dict[str, Any]:
    """Return a single exact-project K3s cluster with bounded non-sensitive fields only."""
    if not is_db_available():
        raise McpK3sError("K3s database is unavailable")

    factory = get_session_factory()
    try:
        async with factory() as session:
            stmt = select(K3sCluster).where(
                K3sCluster.id == cluster_id,
                K3sCluster.project_id == project_id,
                K3sCluster.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            cluster = result.scalar_one_or_none()
            if cluster is None:
                raise McpK3sError("K3s cluster not found")
            return _safe_cluster(cluster, project_id=project_id)
    except Exception as exc:
        if isinstance(exc, McpK3sError):
            raise
        raise McpK3sError("K3s cluster query failed") from exc
