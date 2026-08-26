from typing import Any, Literal

from pydantic import BaseModel, Field


class ExportLocation(BaseModel):
    path: str
    preferred: bool = False
    share_instance_id: str | None = None


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
    is_public: bool = False
    # Union 전용 메타데이터
    library_name: str | None = None
    library_version: str | None = None
    built_at: str | None = None
    # 확장 필드 (Manila 상세 정보)
    progress: str | None = None
    user_id: str | None = None
    user_name: str | None = None  # Keystone 이름 해석(best-effort), 실패 시 None
    access_rules_status: str | None = None
    host: str | None = None  # admin 전용 — 비-admin 응답 시 None으로 마스킹
    availability_zone: str | None = None
    share_type_name: str | None = None
    share_network_id: str | None = None
    export_location_details: list[ExportLocation] = []  # path + preferred + instance


class FileStorageDeleteDiagnostic(BaseModel):
    file_storage_id: str
    status: str | None = None
    share_proto: str | None = None
    share_type_name: str | None = None
    share_network_id: str | None = None
    share_instance_ids: list[str] = []
    root_cause_code: Literal[
        "dhss_false_share_network_mismatch",
        "backend_missing_after_failed_create_or_delete",
        "normal_delete_possible",
        "unknown",
    ]
    confidence: Literal["high", "medium", "low"]
    summary: str
    evidence: list[str] = []
    recommended_action: str
    force_delete_available: bool


class FileStorageForceDeleteResult(BaseModel):
    file_storage_id: str
    status: Literal["force_delete_submitted", "already_deleted"]
    diagnostic: FileStorageDeleteDiagnostic | None = None


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
    visibility: str = "public"  # "public" | "private"
    license_type: str | None = None  # e.g. "MIT", "commercial"
    max_concurrent_mounts: int | None = None  # None = unlimited


class VolumeInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    volume_type: str | None = None
    attachments: list[dict] = []
    bootable: bool = False
    volume_image_metadata: dict | None = None


VolumeDeleteRootCause = Literal[
    "already_deleted",
    "attached_volume_delete_blocked",
    "dependent_snapshot_or_backup",
    "recoverable_error_deleting",
    "recoverable_error_state",
    "normal_delete_possible",
    "not_recoverable_status",
    "unknown",
]

VolumeDeleteRecoveryStatus = Literal[
    "deleted",
    "already_deleted",
    "delete_submitted",
    "blocked",
    "failed",
]

VolumeDeleteRecoveryAction = Literal[
    "diagnose",
    "reset_status",
    "delete",
    "verify_after_delete",
    "force_delete",
    "verify_after_force_delete",
]

VolumeDeleteRecoveryStepStatus = Literal["success", "skipped", "failed"]


class VolumeDeleteMessage(BaseModel):
    id: str | None = None
    event_id: str | None = None
    request_id: str | None = None
    message_level: str | None = None
    resource_uuid: str | None = None
    resource_type: str | None = None
    user_message: str | None = None
    created_at: str | None = None


class VolumeDeleteDependency(BaseModel):
    id: str
    status: str | None = None
    name: str | None = None
    kind: Literal["snapshot", "backup"]


class VolumeDeleteDiagnostic(BaseModel):
    volume_id: str
    status: str | None = None
    project_id: str | None = None
    attachments: list[dict] = []
    dependencies: list[VolumeDeleteDependency] = []
    messages: list[VolumeDeleteMessage] = []
    root_cause_code: VolumeDeleteRootCause
    confidence: Literal["high", "medium", "low"]
    summary: str
    evidence: list[str] = []
    recommended_action: str
    recovery_available: bool
    force_delete_available: bool


class VolumeDeleteRecoveryStep(BaseModel):
    action: VolumeDeleteRecoveryAction
    status: VolumeDeleteRecoveryStepStatus
    detail: str | None = None


class VolumeDeleteRecoveryResult(BaseModel):
    volume_id: str
    status: VolumeDeleteRecoveryStatus
    verified_deleted: bool
    final_status: str | None = None
    diagnostic: VolumeDeleteDiagnostic
    steps: list[VolumeDeleteRecoveryStep] = []


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
    auto_gateway: bool = False


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


class AdminNetworkDetail(NetworkDetail):
    provider_network_type: str | None = None
    provider_segmentation_id: int | None = None
    provider_physical_network: str | None = None


class CreateVolumeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    size_gb: int = Field(..., ge=1, le=16384)
    availability_zone: str | None = None


class ExtendVolumeRequest(BaseModel):
    new_size: int = Field(..., gt=0, description="새 용량 (GB), 현재 크기보다 커야 함")


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


class ShareSnapshotRevertRequest(BaseModel):
    share_id: str


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
    # ip 타입 전용 NFS 보안 옵션 (기본값이 보안 권장 설정)
    root_squash: bool = True
    sec_flavor: Literal["sys", "krb5", "krb5i", "krb5p"] = "sys"


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
    instance_id: str | None = None
    instance_name: str | None = None


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
    project_id: str | None = None
    network_names: list[str] = []
    ip_addresses: list[dict] = []  # [{addr, type, network_name}]


class TopologyRouter(BaseModel):
    id: str
    name: str
    status: str
    external_gateway_network_id: str | None = None
    external_gateway_ips: list[str] = []  # GW 외부 고정 IP 목록 (SNAT IP 포함)
    interface_ips: list[dict] = []  # [{ip_address, subnet_id}] 내부 인터페이스 IP
    is_distributed: bool = False  # DVR 여부
    is_ha: bool = False  # HA 여부
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


class TopologyLBMember(BaseModel):
    id: str
    address: str
    protocol_port: int = 0
    status: str = ""
    subnet_id: str | None = None
    pool_id: str
    server_id: str | None = None


class TopologyLBListener(BaseModel):
    id: str
    name: str = ""
    protocol: str = ""
    protocol_port: int = 0
    default_pool_id: str | None = None


class TopologyLoadBalancer(BaseModel):
    id: str
    name: str = ""
    vip_address: str | None = None
    vip_port_id: str | None = None
    vip_subnet_id: str | None = None
    vip_network_id: str | None = None
    provisioning_status: str = ""
    operating_status: str = ""
    project_id: str | None = None
    listeners: list[TopologyLBListener] = []
    members: list[TopologyLBMember] = []


class TopologyData(BaseModel):
    networks: list[TopologyNetwork] = []
    routers: list[TopologyRouter] = []
    instances: list[TopologyInstance] = []
    floating_ips: list[FloatingIpInfo] = []
    load_balancers: list[TopologyLoadBalancer] = []


# ---------------------------------------------------------------------------
# Object Storage (Swift)
# ---------------------------------------------------------------------------


class CreateContainerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ObjectInfo(BaseModel):
    name: str
    bytes: int = 0
    content_type: str = ""
    last_modified: str = ""
    etag: str = ""


class CreateDirectoryRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)


class CopyObjectRequest(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    dest_container: str | None = None


class MoveObjectRequest(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    dest_container: str | None = None


class RenameObjectRequest(BaseModel):
    source: str = Field(..., min_length=1)
    new_name: str = Field(..., min_length=1)


class BulkDeleteRequest(BaseModel):
    objects: list[str] = Field(..., min_length=1, max_length=1000)
    recursive: bool = False
