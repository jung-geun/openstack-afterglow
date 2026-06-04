"""GPU 프로젝트별 Quota 관리 서비스.

DB가 초기화되어 있어야 동작 (is_db_available() 확인 후 호출).

기본 정책: quota 미설정 시 0 (GPU VM 생성 불가). 관리자가 명시적으로 quota를 설정해야 함.
전체 프로젝트 기본 quota는 project_id = "__default__"로 저장.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.database import get_session_factory, is_db_available

_logger = logging.getLogger(__name__)

DEFAULT_PROJECT_ID = "__default__"

_norm_map: dict[str, str] | None = None


def _get_norm_map() -> dict[str, str]:
    """정규화 맵 lazy 로드 (PCI_DEVICE_MAP 기반)."""
    global _norm_map
    if _norm_map is None:
        from app.api.identity.admin_gpu import build_normalized_alias_map

        _norm_map = build_normalized_alias_map()
    return _norm_map


def normalize_gpu_alias(alias: str) -> str:
    """GPU alias를 대표(canonical) 이름으로 정규화.

    예: "RTX-3090" → "RTX3090", "TITAN-X" → "TITAN_X"
    PCI_DEVICE_MAP에 등록되지 않은 alias는 그대로 반환.
    """
    key = alias.replace("-", "").replace("_", "").replace(" ", "").lower()
    return _get_norm_map().get(key, alias)


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
    if not is_db_available():
        return []
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

    conn의 프로젝트와 target project_id가 다른 경우 (admin이 다른 프로젝트 조회)
    all_projects=True + project_id 필터로 해당 프로젝트 서버를 조회.
    반환: {alias: count} (예: {"RTX3090": 2})
    """
    import asyncio

    from app.services import nova

    def _collect():
        conn_project = getattr(conn, "_afterglow_project_id", None)
        if conn_project and conn_project != project_id:
            # admin이 다른 프로젝트를 조회하는 경우
            servers_raw = list(conn.compute.servers(details=True, all_projects=True, project_id=project_id))
        else:
            # 자기 프로젝트 조회
            servers_raw = list(conn.compute.servers(details=True))

        all_flavors = nova.list_flavors(conn)
        flavors_by_id = {f.id: f for f in all_flavors}
        flavors_by_name = {f.name: f for f in all_flavors}
        usage: dict[str, int] = {}
        for s in servers_raw:
            if s.status not in ("ACTIVE", "SHUTOFF", "PAUSED", "SUSPENDED", "RESIZE"):
                continue
            # openstacksdk raw Server 객체에서 flavor 정보 추출
            flavor = s.flavor if hasattr(s, "flavor") else {}
            if isinstance(flavor, dict):
                flavor_id = flavor.get("id", "")
                flavor_name = flavor.get("original_name", "")
            else:
                flavor_id = getattr(s, "flavor_id", "") or ""
                flavor_name = getattr(s, "flavor_name", "") or ""
            fl = flavors_by_id.get(flavor_id)
            if not fl and flavor_name:
                fl = flavors_by_name.get(flavor_name)
            if not fl:
                continue
            for alias, cnt in _parse_alias_counts(fl.extra_specs or {}).items():
                canonical = normalize_gpu_alias(alias)
                usage[canonical] = usage.get(canonical, 0) + cnt
        return usage

    return await asyncio.to_thread(_collect)


async def get_effective_gpu_quotas(project_id: str) -> dict[str, int]:
    """프로젝트의 유효 GPU quota 맵 반환 (프로젝트별 > 기본값 > 0).

    반환: {alias: limit}
    """
    if not is_db_available():
        return {}
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
    raw_requested = _parse_alias_counts(flavor_extra_specs)
    if not raw_requested:
        return True, ""
    # alias 정규화 (RTX-3090 → RTX3090 등)
    requested: dict[str, int] = {}
    for alias, cnt in raw_requested.items():
        canonical = normalize_gpu_alias(alias)
        requested[canonical] = requested.get(canonical, 0) + cnt

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


async def get_all_gpu_aliases() -> list[str]:
    """클러스터의 모든 GPU PCI alias 반환 (flavor extra_specs + Placement API 통합).

    1. Flavor extra_specs의 pci_passthrough:alias (flavor가 있는 GPU)
    2. Placement API의 실제 GPU device → PCI_DEVICE_MAP alias 매핑 (flavor 없는 GPU 포함)
    """
    import asyncio

    from app.config import get_settings
    from app.services import nova

    def _collect():
        import openstack

        s = get_settings()
        admin_conn = openstack.connect(
            load_envvars=False,
            load_yaml_config=False,
            auth_url=s.os_auth_url,
            auth_type="password",
            username=s.os_username,
            password=s.os_password,
            project_name=s.os_project_name,
            user_domain_name=s.os_user_domain_name,
            project_domain_name=s.os_project_domain_name,
            region_name=s.os_region_name,
            api_timeout=30,
            verify=s.ssl_verify,
        )
        try:
            from app.api.identity.admin_gpu import build_device_name_to_alias_map
            from app.services.gpu_inventory import _collect_gpu_hosts

            aliases: set[str] = set()

            # 1) Flavor extra_specs 기반 alias (정규화 적용)
            all_flavors = nova.list_flavors(admin_conn)
            for f in all_flavors:
                for alias in _parse_alias_counts(f.extra_specs or {}):
                    aliases.add(normalize_gpu_alias(alias))

            # 2) Placement API 기반 — 클러스터에 실제 존재하는 GPU device
            device_to_alias = build_device_name_to_alias_map()
            gpu_data = _collect_gpu_hosts(admin_conn)
            for gpu_type in gpu_data.get("gpu_types", []):
                device_name = gpu_type["device_name"]
                alias = device_to_alias.get(device_name)
                if alias:
                    aliases.add(alias)

            return sorted(aliases)
        finally:
            admin_conn.close()

    return await asyncio.to_thread(_collect)


async def get_gpu_aliases_from_flavors() -> list[str]:
    """모든 flavor의 extra_specs에서 고유한 PCI alias 목록 추출.

    flavor extra_specs 조회는 admin 권한이 필요하므로 admin connection을 사용.
    반환: 정렬된 alias 이름 리스트 (예: ["RTX3090", "RTX4090", "GtxTitanX"])
    """
    import asyncio

    from app.config import get_settings
    from app.services import nova

    def _collect():
        s = get_settings()
        # get_admin_connection_for_project()는 project_id(UUID)를 기대하므로
        # admin project는 project_name으로 직접 연결 생성
        import openstack

        admin_conn = openstack.connect(
            load_envvars=False,
            load_yaml_config=False,
            auth_url=s.os_auth_url,
            auth_type="password",
            username=s.os_username,
            password=s.os_password,
            project_name=s.os_project_name,
            user_domain_name=s.os_user_domain_name,
            project_domain_name=s.os_project_domain_name,
            region_name=s.os_region_name,
            api_timeout=30,
            verify=s.ssl_verify,
        )
        try:
            all_flavors = nova.list_flavors(admin_conn)
            aliases: set[str] = set()
            for f in all_flavors:
                for alias in _parse_alias_counts(f.extra_specs or {}):
                    aliases.add(alias)
            return sorted(aliases)
        finally:
            admin_conn.close()

    return await asyncio.to_thread(_collect)
