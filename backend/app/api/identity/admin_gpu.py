"""관리자 GPU 호스트 모니터링 엔드포인트."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CacheMode, cache_mode, get_os_conn, require_admin
from app.services.cache import cached_call, ttl_normal

# FastAPI-free 인벤토리 유틸리티로 이동된 항목들 — 하위 호환을 위해 재export.
from app.services.gpu_inventory import (  # noqa: F401
    PCI_DEVICE_MAP,
    VENDOR_MAP,
    _collect_gpu_hosts,
    _device_name,
    _extract_hostname,
    _find_root_uuid,
    _is_audio_device,
    build_alias_to_device_name_map,
    get_gpu_spec_list,
)

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/gpu-hosts", dependencies=[Depends(require_admin)])
async def list_gpu_hosts(
    conn: openstack.connection.Connection = Depends(get_os_conn), cm: CacheMode = Depends(cache_mode)
):
    """Placement API에서 각 호스트별 GPU 정보 조회."""

    def _collect():
        return _collect_gpu_hosts(conn)

    try:
        return await cached_call(
            "afterglow:admin:gpu_hosts", ttl_normal(), _collect, enabled=cm.enabled, refresh=cm.refresh
        )
    except Exception:
        raise HTTPException(status_code=500, detail="GPU 호스트 조회 실패")


def build_device_name_to_alias_map() -> dict[str, str]:
    """정식 GPU 이름 → 대표 OpenStack PCI alias 매핑 반환.

    예: "RTX 3090" → "RTX3090", "GTX 1080 Ti" → "GTX1080Ti"
    aliases 리스트의 첫 번째 항목을 대표 alias로 사용.
    """
    name_map: dict[str, str] = {}
    for devices in PCI_DEVICE_MAP.values():
        for info in devices.values():
            if info.get("is_audio"):
                continue
            aliases = info.get("aliases", [])
            if aliases:
                name_map[info["name"]] = aliases[0]
    return name_map


def build_normalized_alias_map() -> dict[str, str]:
    """정규화된 alias → 대표(canonical) alias 매핑 반환.

    하이픈, 언더스코어, 공백을 제거하고 소문자로 비교하여
    같은 GPU의 다른 표기(RTX-3090, RTX3090, RTX_3090)를 대표 alias로 통일.
    """
    norm_map: dict[str, str] = {}
    for devices in PCI_DEVICE_MAP.values():
        for info in devices.values():
            if info.get("is_audio"):
                continue
            aliases = info.get("aliases", [])
            if not aliases:
                continue
            canonical = aliases[0]
            # 대표 alias 자체도 등록
            norm_map[canonical.replace("-", "").replace("_", "").replace(" ", "").lower()] = canonical
            for alias in aliases:
                norm_map[alias.replace("-", "").replace("_", "").replace(" ", "").lower()] = canonical
    return norm_map
