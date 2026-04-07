import re
from pydantic import BaseModel
from typing import Optional


class IpAddress(BaseModel):
    addr: str
    type: str = "fixed"  # "fixed" | "floating"
    network_name: str = ""


class ImageInfo(BaseModel):
    id: str
    name: str
    status: str
    size: Optional[int] = None
    min_disk: int = 0
    min_ram: int = 0
    disk_format: Optional[str] = None
    os_type: Optional[str] = None
    os_distro: Optional[str] = None
    created_at: Optional[str] = None
    owner: Optional[str] = None
    visibility: Optional[str] = None


class FlavorInfo(BaseModel):
    id: str
    name: str
    vcpus: int
    ram: int   # MB
    disk: int  # GB
    is_public: bool = True
    extra_specs: dict = {}

    @property
    def is_gpu(self) -> bool:
        return self.name.startswith("gpu.")

    @property
    def gpu_count(self) -> int:
        m = re.match(r'^gpu\.\w+?(?:x(\d+))?_', self.name)
        if not m:
            return 0
        return int(m.group(1)) if m.group(1) else 1


class InstanceInfo(BaseModel):
    id: str
    name: str
    status: str
    image_id: Optional[str] = None
    image_name: Optional[str] = None
    flavor_id: Optional[str] = None
    flavor_name: Optional[str] = None
    ip_addresses: list[IpAddress] = []
    created_at: Optional[str] = None
    metadata: dict = {}
    # Union 전용 메타데이터
    union_libraries: list[str] = []
    union_strategy: Optional[str] = None   # "prebuilt" | "dynamic"
    union_share_ids: list[str] = []
    union_upper_volume_id: Optional[str] = None
    key_name: Optional[str] = None
    user_id: Optional[str] = None


class CreateInstanceRequest(BaseModel):
    name: str
    image_id: str
    flavor_id: str
    libraries: list[str] = []
    strategy: Optional[str] = None   # "prebuilt" | "dynamic" | None (no libraries)
    network_id: Optional[str] = None
    key_name: Optional[str] = None
    admin_pass: Optional[str] = None
    availability_zone: Optional[str] = None
    boot_volume_size_gb: Optional[int] = None
    additional_volume_ids: list[str] = []
    new_volumes: list[dict] = []
