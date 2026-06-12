"""관리자 GPU 호스트 모니터링 엔드포인트."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

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


class GpuDeviceRequest(BaseModel):
    """GPU 장치 카탈로그 단건 추가/수정 요청."""

    vendor_id: str = Field(..., pattern=r"^[0-9A-Fa-f]{4}$")
    device_id: str = Field(..., pattern=r"^[0-9A-Fa-f]{4}$")
    name: str = Field(..., min_length=1, max_length=128)
    is_audio: bool = False
    aliases: list[str] = Field(default_factory=list)


def _require_db():
    from app.database import is_db_available

    if not is_db_available():
        raise HTTPException(status_code=503, detail="DB가 초기화되지 않아 GPU 카탈로그를 변경할 수 없습니다")


@router.get("/gpu-devices", dependencies=[Depends(require_admin)])
async def list_gpu_devices():
    """병합된 GPU 장치 카탈로그 목록 (내장 기본값 + config.toml + DB overlay).

    각 항목의 source: "builtin"(코드 내장) | "config"(config.toml) | "db"(관리자 추가).
    db 항목만 삭제 가능하다.
    """
    from app.database import is_db_available
    from app.services.gpu_catalog import list_db_devices
    from app.services.gpu_inventory import _DEFAULT_PCI_DEVICE_MAP

    db_keys: set[tuple[str, str]] = set()
    if is_db_available():
        try:
            db_keys = {(e["vendor_id"], e["device_id"]) for e in await list_db_devices()}
        except Exception:
            _logger.warning("GPU 카탈로그 DB 조회 실패 — builtin/config만 표시", exc_info=True)

    devices = []
    for vendor_id, vendor_devices in PCI_DEVICE_MAP.items():
        for device_id, info in vendor_devices.items():
            if (vendor_id, device_id) in db_keys:
                source = "db"
            elif device_id in _DEFAULT_PCI_DEVICE_MAP.get(vendor_id, {}):
                source = "builtin"
            else:
                source = "config"
            devices.append(
                {
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "vendor_name": VENDOR_MAP.get(vendor_id, vendor_id),
                    "name": info["name"],
                    "is_audio": info["is_audio"],
                    "aliases": info.get("aliases", []),
                    "source": source,
                }
            )
    devices.sort(key=lambda d: (d["vendor_id"], d["name"]))
    return {"devices": devices}


@router.post("/gpu-devices", dependencies=[Depends(require_admin)])
async def upsert_gpu_device(req: GpuDeviceRequest):
    """GPU 장치 카탈로그 단건 추가/수정 (DB upsert 후 PCI_DEVICE_MAP 즉시 반영)."""
    from app.services.gpu_catalog import refresh_device_map_from_db, upsert_device

    _require_db()
    try:
        result = await upsert_device(req.vendor_id, req.device_id, req.name, req.is_audio, req.aliases)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await refresh_device_map_from_db()
    return result


@router.delete("/gpu-devices/{vendor_id}/{device_id}", dependencies=[Depends(require_admin)], status_code=204)
async def delete_gpu_device(vendor_id: str, device_id: str):
    """GPU 장치 카탈로그 DB 항목 삭제. builtin/config 항목은 삭제 불가."""
    from app.services.gpu_catalog import delete_device, refresh_device_map_from_db

    _require_db()
    deleted = await delete_device(vendor_id, device_id)
    if not deleted:
        vendor_key = vendor_id.upper()
        device_key = device_id.upper()
        if device_key in PCI_DEVICE_MAP.get(vendor_key, {}):
            raise HTTPException(status_code=409, detail="내장 기본값/config.toml 항목은 삭제할 수 없습니다")
        raise HTTPException(status_code=404, detail="해당 GPU 장치가 카탈로그에 없습니다")
    await refresh_device_map_from_db()


@router.post("/gpu-devices/import", dependencies=[Depends(require_admin)])
async def import_gpu_devices(
    file: UploadFile,
    mode: str = Query("replace", pattern="^(replace|upsert)$"),
):
    """CSV 일괄 import. 포맷: vendor_id,device_id,name,is_audio,aliases(세미콜론 구분).

    mode=replace(기본): DB 항목 전체 교체. mode=upsert: 기존 항목 유지하며 병합.
    """
    from app.services.gpu_catalog import bulk_import, parse_csv, refresh_device_map_from_db

    _require_db()
    raw = await file.read()
    if len(raw) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV 파일이 너무 큽니다 (최대 1MB)")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV는 UTF-8 인코딩이어야 합니다")
    try:
        entries = parse_csv(content)
        imported = await bulk_import(entries, mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await refresh_device_map_from_db()
    return {"imported": imported, "mode": mode}


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
