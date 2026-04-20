"""GPU 프로젝트별 Quota 관리 서비스.

DB가 초기화되어 있어야 동작 (is_db_available() 확인 후 호출).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.database import get_session_factory

_logger = logging.getLogger(__name__)


def _parse_alias_counts(extra_specs: dict) -> dict[str, int]:
    """flavor extra_specs의 pci_passthrough:alias에서 PCI alias → count 매핑 반환.

    예: "RTX3090:1,RTX3090Audio:1" → {"RTX3090": 1}  (Audio 제외)
    """
    alias_str = extra_specs.get("pci_passthrough:alias", "")
    result: dict[str, int] = {}
    if not alias_str:
        return result
    for entry in alias_str.split(","):
        entry = entry.strip()
        if ":" not in entry:
            continue
        alias, _, num_str = entry.rpartition(":")
        alias = alias.strip()
        if "audio" in alias.lower():
            continue
        try:
            result[alias] = result.get(alias, 0) + int(num_str)
        except ValueError:
            result[alias] = result.get(alias, 0) + 1
    return result


async def get_project_gpu_quotas(project_id: str) -> list[dict]:
    """프로젝트의 GPU quota 목록 반환."""
    factory = get_session_factory()
    if not factory:
        return []
    from app.models.db import GpuQuota

    async with factory() as session:
        rows = await session.execute(select(GpuQuota).where(GpuQuota.project_id == project_id))
        return [{"gpu_type": r.gpu_type, "limit": r.limit, "id": r.id} for r in rows.scalars().all()]


async def set_project_gpu_quota(project_id: str, gpu_type: str, limit: int) -> dict:
    """프로젝트의 GPU quota upsert."""
    factory = get_session_factory()
    if not factory:
        raise RuntimeError("DB가 초기화되지 않았습니다")
    from app.models.db import GpuQuota

    async with factory() as session, session.begin():
        result = await session.execute(
            select(GpuQuota).where(GpuQuota.project_id == project_id, GpuQuota.gpu_type == gpu_type)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if row:
            row.limit = limit
            row.updated_at = now
        else:
            row = GpuQuota(project_id=project_id, gpu_type=gpu_type, limit=limit, created_at=now, updated_at=now)
            session.add(row)
    return {"project_id": project_id, "gpu_type": gpu_type, "limit": limit}


async def delete_project_gpu_quota(project_id: str, gpu_type: str) -> None:
    """프로젝트의 특정 GPU quota 삭제."""
    factory = get_session_factory()
    if not factory:
        return
    from app.models.db import GpuQuota

    async with factory() as session, session.begin():
        await session.execute(delete(GpuQuota).where(GpuQuota.project_id == project_id, GpuQuota.gpu_type == gpu_type))


async def get_project_gpu_usage(conn, project_id: str) -> dict[str, int]:
    """프로젝트의 현재 GPU 사용량을 인스턴스 flavor 기반으로 집계.

    반환: {alias: count} (예: {"RTX3090": 2})
    """
    import asyncio

    from app.services import nova

    def _collect():
        servers = nova.list_servers(conn)
        all_flavors = nova.list_flavors(conn)
        flavors_by_id = {f.id: f for f in all_flavors}
        flavors_by_name = {f.name: f for f in all_flavors}
        usage: dict[str, int] = {}
        for s in servers:
            if s.status not in ("ACTIVE", "SHUTOFF", "PAUSED", "SUSPENDED", "RESIZE"):
                continue
            fl = flavors_by_id.get(s.flavor_id or "")
            if not fl and getattr(s, "flavor_name", None):
                fl = flavors_by_name.get(s.flavor_name)
            if not fl:
                continue
            for alias, cnt in _parse_alias_counts(fl.extra_specs or {}).items():
                usage[alias] = usage.get(alias, 0) + cnt
        return usage

    return await asyncio.to_thread(_collect)


async def check_gpu_quota(conn, project_id: str, flavor_extra_specs: dict) -> tuple[bool, str]:
    """VM 생성 전 GPU quota 초과 여부 확인.

    반환: (ok: bool, message: str)
    """
    requested = _parse_alias_counts(flavor_extra_specs)
    if not requested:
        return True, ""

    quotas = await get_project_gpu_quotas(project_id)
    if not quotas:
        return True, ""  # quota 미설정 = 무제한

    quota_map = {q["gpu_type"]: q["limit"] for q in quotas}
    usage = await get_project_gpu_usage(conn, project_id)

    for alias, count in requested.items():
        limit = quota_map.get(alias, -1)
        if limit == -1:
            continue  # 해당 타입은 무제한
        current = usage.get(alias, 0)
        if current + count > limit:
            return False, (f"GPU quota 초과: {alias} — 현재 {current}개 사용 중, quota {limit}개, 요청 {count}개")
    return True, ""
