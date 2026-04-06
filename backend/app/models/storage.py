from pydantic import BaseModel
from typing import Optional, Any


class ShareInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    share_proto: str
    export_locations: list[str] = []
    metadata: dict = {}
    # Union 전용 메타데이터
    library_name: Optional[str] = None
    library_version: Optional[str] = None
    built_at: Optional[str] = None


class LibraryConfig(BaseModel):
    id: str           # e.g. "python311"
    name: str         # e.g. "Python 3.11"
    version: str      # e.g. "3.11"
    packages: list[str]   # pip packages to install
    depends_on: list[str] = []   # library ids this depends on
    share_id: Optional[str] = None   # prebuilt share id (Strategy A)
    available_prebuilt: bool = False


class VolumeInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    volume_type: Optional[str] = None
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
    gateway_ip: Optional[str] = None
    dhcp_enabled: bool = True


class RouterInfo(BaseModel):
    id: str
    name: str
    status: str = ""
    project_id: Optional[str] = None
    external_gateway_network_id: Optional[str] = None
    connected_subnet_ids: list[str] = []


class RouterInterface(BaseModel):
    id: str          # port id
    subnet_id: str
    subnet_name: str
    network_id: str
    ip_address: str


class RouterDetail(BaseModel):
    id: str
    name: str
    status: str
    project_id: Optional[str] = None
    external_gateway_network_id: Optional[str] = None
    external_gateway_network_name: Optional[str] = None
    interfaces: list[RouterInterface] = []


class CreateRouterRequest(BaseModel):
    name: str
    external_network_id: Optional[str] = None


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
    name: str
    size_gb: int
    availability_zone: Optional[str] = None


class CreateShareRequest(BaseModel):
    name: str
    size_gb: int
    share_type: str = "cephfstype"
    share_network_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CreateAccessRuleRequest(BaseModel):
    cephx_id: str
    access_level: str = "ro"  # "ro" | "rw"


class CreateNetworkRequest(BaseModel):
    name: str


class CreateSubnetRequest(BaseModel):
    name: str
    cidr: str
    gateway_ip: Optional[str] = None
    enable_dhcp: bool = True


class FloatingIpInfo(BaseModel):
    id: str
    floating_ip_address: str
    fixed_ip_address: Optional[str] = None
    status: str
    port_id: Optional[str] = None
    floating_network_id: str
    project_id: Optional[str] = None


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
    external_gateway_network_id: Optional[str] = None
    connected_subnet_ids: list[str] = []
    dvr_subnet_ids: list[str] = []
    project_id: Optional[str] = None


class TopologyNetwork(BaseModel):
    id: str
    name: str
    status: str
    is_external: bool = False
    is_shared: bool = False
    project_id: Optional[str] = None
    subnet_details: list[SubnetDetail] = []


class TopologyData(BaseModel):
    networks: list[TopologyNetwork] = []
    routers: list[TopologyRouter] = []
    instances: list[TopologyInstance] = []
    floating_ips: list[FloatingIpInfo] = []
