"""관리자 GPU 호스트 모니터링 엔드포인트."""
import asyncio
import copy
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query
import openstack

from app.api.deps import get_os_conn, require_admin
from app.config import load_raw_toml
from app.services.cache import cached_call, ttl_normal

_logger = logging.getLogger(__name__)

router = APIRouter()

VENDOR_MAP = {
    "10DE": "NVIDIA",
    "8086": "Intel",
    "1002": "AMD",
}

# PCI vendor:product → {name, is_audio} 기본 매핑
_DEFAULT_PCI_DEVICE_MAP: dict[str, dict[str, dict]] = {
    "10DE": {
        # === Maxwell ===
        "17C2": {"name": "GTX TITAN X", "is_audio": False},
        "0FB0": {"name": "GM200 Audio", "is_audio": True},
        # === Pascal ===
        "1B06": {"name": "GTX 1080 Ti", "is_audio": False},
        "1B80": {"name": "GTX 1080", "is_audio": False},
        "1B81": {"name": "GTX 1070", "is_audio": False},
        "1B00": {"name": "TITAN X", "is_audio": False},
        "1B02": {"name": "TITAN Xp", "is_audio": False},
        "10EF": {"name": "GP102 Audio", "is_audio": True},
        # === Ampere Consumer ===
        "2204": {"name": "RTX 3090", "is_audio": False},
        "2203": {"name": "RTX 3090 Ti", "is_audio": False},
        "2206": {"name": "RTX 3080 Ti", "is_audio": False},
        "220A": {"name": "RTX 3080", "is_audio": False},
        "2484": {"name": "RTX 3070 Ti", "is_audio": False},
        "2482": {"name": "RTX 3070", "is_audio": False},
        "2504": {"name": "RTX 3060", "is_audio": False},
        "1AEF": {"name": "GA102 Audio", "is_audio": True},
        # === Ada Lovelace Consumer ===
        "2684": {"name": "RTX 4090", "is_audio": False},
        "2704": {"name": "RTX 4080", "is_audio": False},
        "2782": {"name": "RTX 4070 Ti SUPER", "is_audio": False},
        "2783": {"name": "RTX 4070 Ti", "is_audio": False},
        "2786": {"name": "RTX 4070 SUPER", "is_audio": False},
        "2882": {"name": "RTX 4060 Ti", "is_audio": False},
        "22BA": {"name": "AD102 Audio", "is_audio": True},
        "22BE": {"name": "AD107 Audio", "is_audio": True},
        # === Blackwell Consumer ===
        "2B85": {"name": "RTX 5090", "is_audio": False},
        "2B80": {"name": "RTX 5080", "is_audio": False},
        # === Professional / Workstation ===
        "28B0": {"name": "RTX 2000 Ada", "is_audio": False},
        "2230": {"name": "RTX A6000", "is_audio": False},
        "2231": {"name": "RTX A5000", "is_audio": False},
        "26B1": {"name": "L40", "is_audio": False},
        "26B9": {"name": "L40S", "is_audio": False},
        # === Datacenter ===
        "20B0": {"name": "A100 SXM4 40GB", "is_audio": False},
        "20B2": {"name": "A100 SXM4 80GB", "is_audio": False},
        "20B5": {"name": "A100 PCIe", "is_audio": False},
        "20F1": {"name": "A100 PCIe 40GB", "is_audio": False},
        "20B8": {"name": "A10", "is_audio": False},
        "2330": {"name": "H100 SXM5", "is_audio": False},
        "2331": {"name": "H100 PCIe", "is_audio": False},
    },
}


def _load_device_map() -> dict[str, dict[str, dict]]:
    """config.toml의 [[gpu.devices]] 항목으로 기본 맵을 확장하여 반환."""
    device_map = copy.deepcopy(_DEFAULT_PCI_DEVICE_MAP)
    try:
        raw = load_raw_toml()
        for entry in raw.get("gpu", {}).get("devices", []):
            vendor = str(entry.get("vendor_id", "")).upper()
            device = str(entry.get("device_id", "")).upper()
            name = str(entry.get("name", ""))
            is_audio = bool(entry.get("is_audio", False))
            if vendor and device:
                device_map.setdefault(vendor, {})[device] = {"name": name, "is_audio": is_audio}
    except Exception:
        _logger.warning("config.toml gpu.devices 로드 실패 — 기본 맵 사용", exc_info=True)
    return device_map


PCI_DEVICE_MAP = _load_device_map()


def _extract_hostname(name: str) -> str:
    """RP 이름에서 PCI 주소 접미사를 제거하여 호스트명 반환.

    예: "dms-compute10_0000:03:00.0" → "dms-compute10"
    """
    m = re.match(r'^(.+?)_[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d+$', name)
    return m.group(1) if m else name


def _is_audio_device(vendor_id: str, device_id: str) -> bool:
    """PCI 디바이스가 오디오 장치인지 확인."""
    info = PCI_DEVICE_MAP.get(vendor_id, {}).get(device_id)
    if info is not None:
        return info["is_audio"]
    return False


def _device_name(vendor_id: str, device_id: str) -> str:
    """PCI vendor:product → 디바이스 이름."""
    info = PCI_DEVICE_MAP.get(vendor_id, {}).get(device_id)
    if info:
        return info["name"]
    return ""


def _find_root_uuid(uuid: str, rp_map: dict) -> str:
    """RP 트리에서 루트(호스트) UUID를 찾음 (순환 방지 포함)."""
    visited: set[str] = set()
    current = uuid
    while current in rp_map:
        parent = rp_map[current].get("parent_provider_uuid")
        if not parent:
            break
        if parent in visited:
            break
        visited.add(current)
        current = parent
    return current


@router.get("/gpu-hosts", dependencies=[Depends(require_admin)])
async def list_gpu_hosts(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    """Placement API에서 각 호스트별 GPU 정보 조회."""
    def _collect():
        placement_ep = conn.placement.get_endpoint()

        # 1) 모든 리소스 프로바이더 조회
        rps_resp = conn.session.get(f"{placement_ep}/resource_providers")
        all_rps = rps_resp.json().get("resource_providers", [])

        # RP UUID → RP 전체 데이터 맵
        rp_map: dict[str, dict] = {rp["uuid"]: rp for rp in all_rps}

        # 루트 RP (parent_provider_uuid가 None) → 호스트 맵
        host_map: dict[str, dict] = {}
        for rp in all_rps:
            if rp.get("parent_provider_uuid") is None:
                host_map[rp["uuid"]] = {
                    "name": rp["name"],
                    "uuid": rp["uuid"],
                    "gpus": [],
                    "gpu_total": 0,
                    "gpu_used": 0,
                }

        # 2) 루트가 아닌 모든 RP의 인벤토리에서 CUSTOM_PCI_* 스캔
        for rp in all_rps:
            if rp.get("parent_provider_uuid") is None:
                continue  # 루트는 별도 처리

            # 루트 호스트 UUID 탐색
            root_uuid = _find_root_uuid(rp["uuid"], rp_map)
            if root_uuid not in host_map:
                continue

            try:
                inv_resp = conn.session.get(
                    f"{placement_ep}/resource_providers/{rp['uuid']}/inventories"
                )
                inventories = inv_resp.json().get("inventories", {})

                # usages 별도 조회 (inventory에는 used 필드가 없음)
                usages: dict[str, int] = {}
                has_pci = any(rc.startswith("CUSTOM_PCI_") for rc in inventories)
                if has_pci:
                    try:
                        usage_resp = conn.session.get(
                            f"{placement_ep}/resource_providers/{rp['uuid']}/usages"
                        )
                        usages = usage_resp.json().get("usages", {})
                    except Exception:
                        pass

                for rc_name, inv_data in inventories.items():
                    if not rc_name.startswith("CUSTOM_PCI_"):
                        continue

                    parts = rc_name.split("_")  # ["CUSTOM", "PCI", "10DE", "10EF"]
                    vendor_id = parts[2] if len(parts) >= 3 else ""
                    device_id = parts[3] if len(parts) >= 4 else ""

                    if _is_audio_device(vendor_id, device_id):
                        continue

                    # PCI 주소: rp 이름에서 루트 호스트 이름 제거
                    root_name = host_map[root_uuid]["name"]
                    rp_name = rp["name"]
                    pci_address = rp_name
                    if rp_name.startswith(root_name + "_"):
                        pci_address = rp_name[len(root_name) + 1:]

                    used = usages.get(rc_name, 0)
                    gpu_info = {
                        "provider_name": rp_name,
                        "provider_uuid": rp["uuid"],
                        "pci_address": pci_address,
                        "resource_class": rc_name,
                        "vendor_id": vendor_id,
                        "vendor_name": VENDOR_MAP.get(vendor_id, vendor_id),
                        "device_id": device_id,
                        "device_name": _device_name(vendor_id, device_id),
                        "total": inv_data.get("total", 0),
                        "used": used,
                        "allocation_ratio": inv_data.get("allocation_ratio", 1.0),
                        "reserved": inv_data.get("reserved", 0),
                    }

                    host_map[root_uuid]["gpus"].append(gpu_info)
                    host_map[root_uuid]["gpu_total"] += gpu_info["total"]
                    host_map[root_uuid]["gpu_used"] += gpu_info["used"]
            except Exception:
                _logger.warning(
                    "RP %s 인벤토리 조회 실패", rp.get("uuid"), exc_info=True
                )

        # 3) 자식 RP에서 GPU를 찾지 못한 호스트: 루트 RP 인벤토리도 확인
        for host_uuid, host_info in host_map.items():
            if host_info["gpu_total"] > 0:
                continue
            try:
                inv_resp = conn.session.get(
                    f"{placement_ep}/resource_providers/{host_uuid}/inventories"
                )
                inventories = inv_resp.json().get("inventories", {})

                usages: dict[str, int] = {}
                has_pci = any(rc.startswith("CUSTOM_PCI_") for rc in inventories)
                if has_pci:
                    try:
                        usage_resp = conn.session.get(
                            f"{placement_ep}/resource_providers/{host_uuid}/usages"
                        )
                        usages = usage_resp.json().get("usages", {})
                    except Exception:
                        pass

                for rc_name, inv_data in inventories.items():
                    if not rc_name.startswith("CUSTOM_PCI_"):
                        continue
                    parts = rc_name.split("_")
                    vendor_id = parts[2] if len(parts) >= 3 else ""
                    device_id = parts[3] if len(parts) >= 4 else ""
                    if _is_audio_device(vendor_id, device_id):
                        continue
                    used = usages.get(rc_name, 0)
                    gpu_info = {
                        "provider_name": host_info["name"],
                        "provider_uuid": host_uuid,
                        "pci_address": "host-level",
                        "resource_class": rc_name,
                        "vendor_id": vendor_id,
                        "vendor_name": VENDOR_MAP.get(vendor_id, vendor_id),
                        "device_id": device_id,
                        "device_name": _device_name(vendor_id, device_id),
                        "total": inv_data.get("total", 0),
                        "used": used,
                        "allocation_ratio": inv_data.get("allocation_ratio", 1.0),
                        "reserved": inv_data.get("reserved", 0),
                    }
                    host_info["gpus"].append(gpu_info)
                    host_info["gpu_total"] += gpu_info["total"]
                    host_info["gpu_used"] += gpu_info["used"]
            except Exception:
                _logger.warning(
                    "루트 RP %s 인벤토리 조회 실패", host_uuid, exc_info=True
                )

        # GPU가 있는 호스트만 필터링하여 정렬
        gpu_hosts = sorted(
            [h for h in host_map.values() if h["gpu_total"] > 0],
            key=lambda h: h["name"],
        )

        total_gpus = sum(h["gpu_total"] for h in gpu_hosts)
        used_gpus = sum(h["gpu_used"] for h in gpu_hosts)

        # GPU 종류별 집계
        type_map: dict[str, dict] = {}
        for h in gpu_hosts:
            for gpu in h["gpus"]:
                key = f"{gpu['vendor_id']}_{gpu['device_id']}"
                if key not in type_map:
                    type_map[key] = {
                        "device_name": gpu["device_name"] or gpu["device_id"],
                        "vendor": gpu["vendor_name"],
                        "total": 0,
                        "used": 0,
                    }
                type_map[key]["total"] += gpu["total"]
                type_map[key]["used"] += gpu["used"]

        gpu_types = sorted(type_map.values(), key=lambda x: x["total"], reverse=True)

        # 호스트명 기반 집계 (PCI 주소 접미사 제거 후 그룹핑)
        agg: dict[str, dict] = {}
        for h in gpu_hosts:
            hostname = _extract_hostname(h["name"])
            if hostname not in agg:
                agg[hostname] = {
                    "name": hostname,
                    "gpus": [],
                    "gpu_groups": [],
                    "gpu_total": 0,
                    "gpu_used": 0,
                }
            agg[hostname]["gpus"].extend(h["gpus"])
            agg[hostname]["gpu_total"] += h["gpu_total"]
            agg[hostname]["gpu_used"] += h["gpu_used"]

        for host_data in agg.values():
            groups: dict[str, dict] = {}
            for gpu in host_data["gpus"]:
                key = f"{gpu['vendor_id']}_{gpu['device_id']}"
                if key not in groups:
                    groups[key] = {
                        "device_name": gpu["device_name"] or gpu["device_id"],
                        "vendor_name": gpu["vendor_name"],
                        "total": 0,
                        "used": 0,
                    }
                groups[key]["total"] += gpu["total"]
                groups[key]["used"] += gpu["used"]
            host_data["gpu_groups"] = sorted(groups.values(), key=lambda x: x["device_name"])

        aggregated_hosts = sorted(agg.values(), key=lambda h: h["name"])

        return {
            "hosts": gpu_hosts,
            "aggregated_hosts": aggregated_hosts,
            "summary": {
                "total_hosts": len(aggregated_hosts),
                "total_gpus": total_gpus,
                "used_gpus": used_gpus,
                "available_gpus": total_gpus - used_gpus,
            },
            "gpu_types": gpu_types,
        }

    try:
        return await cached_call("union:admin:gpu_hosts", ttl_normal(), _collect, refresh=refresh)
    except Exception:
        raise HTTPException(status_code=500, detail="GPU 호스트 조회 실패")
