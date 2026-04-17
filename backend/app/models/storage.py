from typing import Any, Literal

from pydantic import BaseModel, Field


class FileStorageInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    share_proto: str
    export_locations: list[str] = []
    metadata: dict = {}
    project_id: str | None = None
    created_at: str | None = None
    nfs_export_location: str | None = None
    # Union 전용 메타데이터
    library_name: str | None = None
    library_version: str | None = None
    built_at: str | None = None


class LibraryConfig(BaseModel):
    id: str  # e.g. "python311"
    name: str  # e.g. "Python 3.11"
    version: str  # e.g. "3.11"
    packages: list[str]  # pip packages to install
    depends_on: list[str] = []  # library ids this depends on
    file_storage_id: str | None = None  # prebuilt file storage id (Strategy A)
    available_prebuilt: bool = False
    share_proto: str = "CEPHFS"  # CEPHFS | NFS
    ubuntu_versions: list[str] = ["22.04", "24.04"]  # 지원 Ubuntu 버전


class VolumeInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    volume_type: str | None = None
    attachments: list[dict] = []


class NetworkInfo(BaseModel):
    id: str
    name: str
    status: str
    subnets: list[str] = []
    is_external: bool = False
    is_shared: bool = False


class SubnetDetail(BaseModel):
    id: str
    name: str
    cidr: str
    gateway_ip: str | None = None
    dhcp_enabled: bool = True


class RouterInfo(BaseModel):
    id: str
    name: str
    status: str = ""
    project_id: str | None = None
    external_gateway_network_id: str | None = None
    connected_subnet_ids: list[str] = []


class RouterInterface(BaseModel):
    id: str  # port id
    subnet_id: str
    subnet_name: str
    network_id: str
    ip_address: str


class RouterDetail(BaseModel):
    id: str
    name: str
    status: str
    project_id: str | None = None
    external_gateway_network_id: str | None = None
    external_gateway_network_name: str | None = None
    interfaces: list[RouterInterface] = []


class CreateRouterRequest(BaseModel):
    name: str
    external_network_id: str | None = None


class RouterInterfaceRequest(BaseModel):
    subnet_id: str


class RouterGatewayRequest(BaseModel):
    external_network_id: str


class NetworkDetail(BaseModel):
    id: str
    name: str
    status: str
    subnets: list[str] = []
    is_external: bool = False
    is_shared: bool = False
    subnet_details: list[SubnetDetail] = []
    routers: list[RouterInfo] = []


class CreateVolumeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    size_gb: int = Field(..., ge=1, le=16384)
    availability_zone: str | None = None


class CreateFileStorageRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    size_gb: int = Field(..., ge=1, le=16384)
    share_type: str = Field("", max_length=255)
    share_network_id: str | None = None
    metadata: dict[str, Any] | None = None
    share_proto: Literal["CEPHFS", "NFS"] = "CEPHFS"


class ShareNetworkInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    neutron_net_id: str | None = None
    neutron_subnet_id: str | None = None
    network_type: str | None = None
    status: str = ""
    created_at: str | None = None
    security_service_ids: list[str] = []


class CreateShareNetworkRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    neutron_net_id: str
    neutron_subnet_id: str


class ShareSnapshotInfo(BaseModel):
    id: str
    name: str
    status: str
    share_id: str
    size: int = 0
    description: str | None = None
    created_at: str | None = None


class CreateShareSnapshotRequest(BaseModel):
    share_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class SecurityServiceInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str  # ldap | kerberos | active_directory
    dns_ip: str | None = None
    server: str | None = None
    domain: str | None = None
    status: str = ""
    created_at: str | None = None


class CreateSecurityServiceRequest(BaseModel):
    type: Literal["ldap", "kerberos", "active_directory"]
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    dns_ip: str = ""
    server: str = ""
    domain: str = ""
    user: str = ""
    password: str = ""


class CreateAccessRuleRequest(BaseModel):
    access_to: str = Field(..., min_length=1, max_length=255)  # CephX ID 또는 IP/CIDR
    access_level: Literal["ro", "rw"] = "ro"
    access_type: Literal["cephx", "ip"] = "cephx"


class UpdateSubnetRequest(BaseModel):
    name: str | None = None
    gateway_ip: str | None = None
    enable_dhcp: bool | None = None


class CreateNetworkRequest(BaseModel):
    name: str


class CreateSubnetRequest(BaseModel):
    name: str
    cidr: str
    gateway_ip: str | None = None
    enable_dhcp: bool = True


class FloatingIpInfo(BaseModel):
    id: str
    floating_ip_address: str
    fixed_ip_address: str | None = None
    status: str = ""
    port_id: str | None = None
    floating_network_id: str
    project_id: str | None = None


class AssociateFipRequest(BaseModel):
    instance_id: str


class CreateFipRequest(BaseModel):
    floating_network_id: str


# ---------------------------------------------------------------------------
# 글로벌 토폴로지
# ---------------------------------------------------------------------------


class TopologyInstance(BaseModel):
    id: str
    name: str
    status: str
    network_names: list[str] = []
    ip_addresses: list[dict] = []  # [{addr, type, network_name}]


class TopologyRouter(BaseModel):
    id: str
    name: str
    status: str
    external_gateway_network_id: str | None = None
    connected_subnet_ids: list[str] = []
    dvr_subnet_ids: list[str] = []
    project_id: str | None = None


class TopologyNetwork(BaseModel):
    id: str
    name: str
    status: str
    is_external: bool = False
    is_shared: bool = False
    project_id: str | None = None
    subnet_details: list[SubnetDetail] = []


class TopologyData(BaseModel):
    networks: list[TopologyNetwork] = []
    routers: list[TopologyRouter] = []
    instances: list[TopologyInstance] = []
    floating_ips: list[FloatingIpInfo] = []
