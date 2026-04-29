from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends

from app.api.deps import get_os_conn
from app.database import is_db_available
from app.models.compute import FlavorInfo
from app.services import nova

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get("", response_model=list[FlavorInfo])
async def list_flavors(conn: openstack.connection.Connection = Depends(get_os_conn)):
    flavors = nova.list_flavors(conn)

    # GPU 쿼터 기반 필터링: 프로젝트에 쿼터가 없는(0) GPU flavor 제외
    if is_db_available():
        try:
            from app.services.gpu_quota import get_effective_gpu_quotas, normalize_gpu_alias

            project_id = conn._afterglow_project_id
            quotas = await get_effective_gpu_quotas(project_id)

            def _has_gpu_access(f: FlavorInfo) -> bool:
                alias_str = f.extra_specs.get("pci_passthrough:alias", "")
                if not alias_str:
                    return True  # GPU가 아닌 flavor는 통과
                for entry in alias_str.split(","):
                    entry = entry.strip()
                    if ":" not in entry:
                        continue
                    alias = entry.rpartition(":")[0].strip()
                    if "audio" in alias.lower():
                        continue
                    canonical = normalize_gpu_alias(alias)
                    if quotas.get(canonical, 0) == 0:
                        return False
                return True

            flavors = [f for f in flavors if _has_gpu_access(f)]
        except Exception:
            _logger.warning("GPU 쿼터 기반 flavor 필터링 실패 — 전체 목록 반환", exc_info=True)

    return flavors
