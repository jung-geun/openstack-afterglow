from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends

from app.api.deps import CacheMode, cache_mode, get_os_conn
from app.models.compute import FlavorInfo
from app.services import cache, nova
from app.services.cache import keys

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get("", response_model=list[FlavorInfo])
async def list_flavors(
    conn: openstack.connection.Connection = Depends(get_os_conn),
    cm: CacheMode = Depends(cache_mode),
):
    pid = conn._afterglow_project_id
    key = keys.project_key("nova", pid, "flavors")

    async def _load() -> list[FlavorInfo]:
        all_flavors = await asyncio.to_thread(nova.list_flavors, conn)

        # GPU 쿼터 기반 필터링: 프로젝트에 쿼터가 없는(0) GPU flavor 제외
        try:
            from drover_sdk import register as register_drover

            from app.services.gpu_inventory import is_gpu_flavor, normalize_gpu_alias

            quotas = await asyncio.to_thread(register_drover(conn).effective_gpu_quotas)
            if not isinstance(quotas, dict):
                raise ValueError("effective_gpu_quotas response is not a dict")

            def _has_gpu_access(f: FlavorInfo) -> bool:
                if not is_gpu_flavor(f):
                    return True
                alias_str = f.extra_specs.get("pci_passthrough:alias", "")
                if not alias_str:
                    return quotas.get("gpu", 0) > 0 or quotas.get("default", 0) > 0
                for entry in alias_str.split(","):
                    entry = entry.strip()
                    if not entry or not is_gpu_flavor(extra_specs={"pci_passthrough:alias": entry}):
                        continue
                    alias = entry.rpartition(":")[0].strip() if ":" in entry else entry
                    canonical = normalize_gpu_alias(alias)
                    if quotas.get(canonical, 0) == 0:
                        return False
                return True

            return [f for f in all_flavors if _has_gpu_access(f)]
        except Exception:
            _logger.warning("GPU 쿼터 기반 flavor 필터링 실패 — non-GPU 목록만 반환", exc_info=True)
            from app.services.gpu_inventory import is_gpu_flavor

            return [f for f in all_flavors if not is_gpu_flavor(f)]

    return await cache.cached_call(key, cache.ttl_static(), _load, enabled=cm.enabled, refresh=cm.refresh)
