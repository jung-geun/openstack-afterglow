"""관리자 GPU 호스트 모니터링 엔드포인트."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn, require_admin

_logger = logging.getLogger(__name__)

router = APIRouter()

VENDOR_MAP = {
    "10DE": "NVIDIA",
    "8086": "Intel",
    "1002": "AMD",
}

# PCI vendor:product → {name, is_audio} 매핑
# nova.conf의 alias 설정 기반으로 정의
PCI_DEVICE_MAP: dict[str, dict[str, dict]] = {
    "10DE": {
        "17C2": {"name": "GTX TITAN X", "is_audio": False},
        "0FB0": {"name": "GM200 Audio", "is_audio": True},
        "1B06": {"name": "GTX 1080 Ti", "is_audio": False},
        "1B00": {"name": "TITAN X", "is_audio": False},
        "10EF": {"name": "GP102 Audio", "is_audio": True},
        "2204": {"name": "RTX 3090", "is_audio": False},
        "2203": {"name": "RTX 3090 Ti", "is_audio": False},
        "1AEF": {"name": "GA102 Audio", "is_audio": True},
        "2684": {"name": "RTX 4090", "is_audio": False},
        "22BA": {"name": "AD102 Audio", "is_audio": True},
        "28B0": {"name": "RTX 2000 Ada", "is_audio": False},
        "22BE": {"name": "AD107 Audio", "is_audio": True},
    },
}


def _is_audio_device(vendor_id: str, device_id: str) -> bool:
    """PCI 디바이스가 오디오 장치인지 확인."""
    info = PCI_DEVICE_MAP.get(vendor_id, {}).get(device_id)
    if info is not None:
        return info["is_audio"]
    # 매핑 없을 경우: Audio 클래스 product ID는 오디오로 간주
    return False


def _device_name(vendor_id: str, device_id: str) -> str:
    """PCI vendor:product → 디바이스 이름."""
    info = PCI_DEVICE_MAP.get(vendor_id, {}).get(device_id)
    if info:
        return info["name"]
    return ""


@router.get("/gpu-hosts", dependencies=[Depends(require_admin)])
async def list_gpu_hosts(conn: openstack.connection.Connection = Depends(get_os_conn)):
    """Placement API에서 각 호스트별 GPU 정보 조회."""
    def _collect():
        placement_ep = conn.placement.get_endpoint()

        # 1) 모든 리소스 프로바이더 조회
        rps_resp = conn.session.get(f"{placement_ep}/resource_providers")
        rps = rps_resp.json().get("resource_providers", [])

        # 부모(호스트)와 자식(GPU) 분리
        # parent_provider_uuid가 None이면 호스트, 아니면 GPU 자식
        host_map: dict[str, dict] = {}  # uuid -> {name, uuid, gpus: []}
        child_rps: list[dict] = []

        for rp in rps:
            parent_uuid = rp.get("parent_provider_uuid")
            if parent_uuid is None:
                # 최상위 프로바이더 (호스트)
                host_map[rp["uuid"]] = {
                    "name": rp["name"],
                    "uuid": rp["uuid"],
                    "gpus": [],
                    "gpu_total": 0,
                    "gpu_used": 0,
                }
            else:
                # 자식 프로바이더 (GPU 등)
                child_rps.append(rp)

        # 2) 각 자식 RP의 인벤토리에서 CUSTOM_PCI_* 리소스 클래스 찾기
        for child in child_rps:
            parent_uuid = child.get("parent_provider_uuid", "")
            if parent_uuid not in host_map:
                continue

            try:
                inv_resp = conn.session.get(
                    f"{placement_ep}/resource_providers/{child['uuid']}/inventories"
                )
                inventories = inv_resp.json().get("inventories", {})

                for rc_name, inv_data in inventories.items():
                    if not rc_name.startswith("CUSTOM_PCI_"):
                        continue

                    # 리소스 클래스에서 vendor_id, device_id 추출
                    # CUSTOM_PCI_10DE_10EF → vendor=10DE, device=10EF
                    parts = rc_name.split("_")  # ["CUSTOM", "PCI", "10DE", "10EF"]
                    vendor_id = parts[2] if len(parts) >= 3 else ""
                    device_id = parts[3] if len(parts) >= 4 else ""

                    # 오디오 디바이스 제외
                    if _is_audio_device(vendor_id, device_id):
                        continue

                    # PCI 주소 추출: 자식 RP 이름에서 부모 이름 제거
                    parent_name = host_map[parent_uuid]["name"]
                    child_name = child["name"]
                    pci_address = child_name
                    if child_name.startswith(parent_name + "_"):
                        pci_address = child_name[len(parent_name) + 1:]

                    gpu_info = {
                        "provider_name": child_name,
                        "provider_uuid": child["uuid"],
                        "pci_address": pci_address,
                        "resource_class": rc_name,
                        "vendor_id": vendor_id,
                        "vendor_name": VENDOR_MAP.get(vendor_id, vendor_id),
                        "device_id": device_id,
                        "device_name": _device_name(vendor_id, device_id),
                        "total": inv_data.get("total", 0),
                        "used": inv_data.get("used", 0),
                        "allocation_ratio": inv_data.get("allocation_ratio", 1.0),
                        "reserved": inv_data.get("reserved", 0),
                    }

                    host_map[parent_uuid]["gpus"].append(gpu_info)
                    host_map[parent_uuid]["gpu_total"] += gpu_info["total"]
                    host_map[parent_uuid]["gpu_used"] += gpu_info["used"]
            except Exception:
                _logger.warning(
                    "GPU 프로바이더 %s 인벤토리 조회 실패", child.get("uuid"), exc_info=True
                )

        # 3) 자식 RP에서 GPU를 찾지 못한 호스트는 루트 RP 인벤토리도 확인
        # (일부 OpenStack 배포에서는 PCI 리소스가 호스트 RP에 직접 등록됨)
        for host_uuid, host_info in host_map.items():
            if host_info["gpu_total"] > 0:
                continue  # 이미 자식 RP에서 찾았으면 스킵
            try:
                inv_resp = conn.session.get(
                    f"{placement_ep}/resource_providers/{host_uuid}/inventories"
                )
                inventories = inv_resp.json().get("inventories", {})
                for rc_name, inv_data in inventories.items():
                    if not rc_name.startswith("CUSTOM_PCI_"):
                        continue
                    parts = rc_name.split("_")
                    vendor_id = parts[2] if len(parts) >= 3 else ""
                    device_id = parts[3] if len(parts) >= 4 else ""
                    if _is_audio_device(vendor_id, device_id):
                        continue
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
                        "used": inv_data.get("used", 0),
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

        return {
            "hosts": gpu_hosts,
            "summary": {
                "total_hosts": len(gpu_hosts),
                "total_gpus": total_gpus,
                "used_gpus": used_gpus,
                "available_gpus": total_gpus - used_gpus,
            },
        }

    try:
        return await asyncio.to_thread(_collect)
    except Exception:
        raise HTTPException(status_code=500, detail="GPU 호스트 조회 실패")