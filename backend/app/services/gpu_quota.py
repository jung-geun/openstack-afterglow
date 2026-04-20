"""GPU 프로젝트별 Quota 관리 서비스.

DB가 초기화되어 있어야 동작 (is_db_available() 확인 후 호출).

기본 정책: quota 미설정 시 0 (GPU VM 생성 불가). 관리자가 명시적으로 quota를 설정해야 함.
전체 프로젝트 기본 quota는 project_id = "__default__"로 저장.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.database import get_session_factory

_logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "__default__"


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


async def get_effective_gpu_quotas(project_id: str) -> dict[str, int]:
    """프로젝트의 유효 GPU quota 맵 반환 (프로젝트별 > 기본값 > 0).

    반환: {alias: limit}
    """
    project_quotas = await get_project_gpu_quotas(project_id)
    default_quotas = await get_project_gpu_quotas(DEFAULT_PROJECT_ID)

    default_map = {q["gpu_type"]: q["limit"] for q in default_quotas}
    effective: dict[str, int] = dict(default_map)

    # 프로젝트별 설정이 기본값을 오버라이드
    for q in project_quotas:
        effective[q["gpu_type"]] = q["limit"]

    return effective


async def check_gpu_quota(conn, project_id: str, flavor_extra_specs: dict) -> tuple[bool, str]:
    """VM 생성 전 GPU quota 초과 여부 확인.

    기본 정책: quota 미설정 시 0 (거부). 관리자가 명시적으로 설정해야 허용.
    반환: (ok: bool, message: str)
    """
    requested = _parse_alias_counts(flavor_extra_specs)
    if not requested:
        return True, ""

    effective = await get_effective_gpu_quotas(project_id)
    usage = await get_project_gpu_usage(conn, project_id)

    for alias, count in requested.items():
        limit = effective.get(alias, 0)  # 미설정 = 0 (거부)
        if limit == -1:
            continue  # 무제한
        current = usage.get(alias, 0)
        if current + count > limit:
            if limit == 0:
                return False, f"GPU quota 미할당: {alias} — 관리자에게 GPU quota 요청이 필요합니다"
            return False, f"GPU quota 초과: {alias} — 현재 {current}개 사용 중, quota {limit}개, 요청 {count}개"
    return True, ""


async def get_gpu_aliases_from_flavors(conn) -> list[str]:
    """모든 flavor의 extra_specs에서 고유한 PCI alias 목록 추출.

    반환: 정렬된 alias 이름 리스트 (예: ["RTX3090", "RTX4090", "GtxTitanX"])
    """
    import asyncio

    from app.services import nova

    def _collect():
        all_flavors = nova.list_flavors(conn)
        aliases: set[str] = set()
        for f in all_flavors:
            for alias in _parse_alias_counts(f.extra_specs or {}):
                aliases.add(alias)
        return sorted(aliases)

    return await asyncio.to_thread(_collect)
