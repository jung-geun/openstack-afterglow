import re

from pydantic import BaseModel, Field, field_validator


class IpAddress(BaseModel):
    addr: str
    type: str = "fixed"  # "fixed" | "floating"
    network_name: str = ""


class ImageInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int | None = None
    min_disk: int = 0
    min_ram: int = 0
    disk_format: str | None = None
    os_type: str | None = None
    os_distro: str | None = None
    created_at: str | None = None
    owner: str | None = None
    visibility: str | None = None


class ImageDetail(ImageInfo):
    checksum: str | None = None
    container_format: str | None = None
    virtual_size: int | None = None
    updated_at: str | None = None
    protected: bool = False
    tags: list[str] = []
    properties: dict = {}
    os_hash_algo: str | None = None
    os_hash_value: str | None = None
    direct_url: str | None = None


class FlavorInfo(BaseModel):
    id: str
    name: str
    vcpus: int
    ram: int  # MB
    disk: int  # GB
    is_public: bool = True
    extra_specs: dict = {}

    @property
    def is_gpu(self) -> bool:
        return self.name.startswith("gpu.")

    @property
    def gpu_count(self) -> int:
        m = re.match(r"^gpu\.\w+?(?:x(\d+))?_", self.name)
        if not m:
            return 0
        return int(m.group(1)) if m.group(1) else 1


class InstanceInfo(BaseModel):
    id: str
    name: str
    status: str
    image_id: str | None = None
    image_name: str | None = None
    flavor_id: str | None = None
    flavor_name: str | None = None
    ip_addresses: list[IpAddress] = []
    created_at: str | None = None
    metadata: dict = {}
    # Union 전용 메타데이터
    union_libraries: list[str] = []
    union_strategy: str | None = None  # "prebuilt" | "dynamic"
    union_share_ids: list[str] = []
    union_upper_volume_id: str | None = None
    key_name: str | None = None
    user_id: str | None = None


class CreateInstanceRequest(BaseModel):
    name: str
    image_id: str
    flavor_id: str
    libraries: list[str] = []
    strategy: str | None = None  # "prebuilt" | "dynamic" | None (no libraries)
    network_id: str | None = None
    key_name: str | None = None
    admin_pass: str | None = Field(None, min_length=8, max_length=128)
    availability_zone: str | None = None
    boot_volume_size_gb: int | None = Field(None, ge=1, le=16384)
    delete_boot_volume_on_termination: bool = False
    additional_volume_ids: list[str] = []
    new_volumes: list["NewVolumeRequest"] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$", v):
            raise ValueError("name은 영문자/숫자로 시작하고, 영문자·숫자·하이픈·언더스코어만 허용되며 최대 63자입니다")
        return v


class NewVolumeRequest(BaseModel):
    name: str = ""
    size_gb: int = 50

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if v and not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,254}$", v):
            raise ValueError("볼륨 이름은 영문자/숫자로 시작해야 합니다")
        return v

    @field_validator("size_gb")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v < 1 or v > 16384:
            raise ValueError("볼륨 크기는 1~16384 GB 범위여야 합니다")
        return v


class AttachVolumeRequest(BaseModel):
    volume_id: str


class AttachInterfaceRequest(BaseModel):
    net_id: str


class UpdateSecurityGroupsRequest(BaseModel):
    security_group_ids: list[str] = []
