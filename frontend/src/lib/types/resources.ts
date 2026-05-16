// 공통 타입 허브 — 각 파일에서 자체 인터페이스 대신 이곳에서 import

export interface IpAddress {
  addr: string;
  type: string;
  network_name: string;
}

export interface Instance {
  id: string;
  name: string;
  status: string;
  image_id: string | null;
  image_name: string | null;
  flavor_id: string | null;
  flavor_name: string | null;
  ip_addresses: IpAddress[];
  created_at: string | null;
  metadata: Record<string, string>;
  union_libraries: string[];
  union_strategy: string | null;
  union_share_ids: string[];
  union_upper_volume_id: string | null;
  key_name: string | null;
  user_id: string | null;
  fault?: { message?: string; code?: number; created?: string } | null;
}

export interface Volume {
  id: string;
  name: string;
  status: string;
  size: number;
  volume_type: string | null;
  attachments: Record<string, unknown>[];
  bootable?: boolean;
  volume_image_metadata?: Record<string, string> | null;
}

export interface VolumeAttachment {
  id: string;
  volume_id: string;
  device: string;
  name?: string;
  size?: number;
  status?: string;
  delete_on_termination?: boolean;
}

export interface FileStorage {
  id: string;
  name: string;
  status: string;
  size: number;
  share_proto: string;
  export_locations: string[];
  metadata: Record<string, string>;
  library_name: string | null;
  library_version: string | null;
  built_at: string | null;
}

export interface AccessRule {
  id: string;
  access_type: string;
  access_to: string;
  access_level: string;
  access_key: string | null;
  state: string;
}

export interface Network {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
}

// 라우트/컴포넌트에서 공통으로 쓰는 간결한 네트워크 정보
export interface NetworkInfo {
  id: string;
  name: string;
  status?: string;
  is_external?: boolean;
  is_shared?: boolean;
}

export interface SubnetInfo {
  id: string;
  cidr?: string;
  name?: string;
}

export interface PortInfo {
  id: string;
  network_id: string;
  mac_address: string;
  fixed_ips: { ip_address: string; subnet_id: string }[];
  security_group_ids: string[];
  status: string;
  name?: string;
  device_owner?: string;
  device_id?: string;
  project_id?: string | null;
}

export interface SecurityGroupRule {
  id: string;
  direction: string;
  protocol: string | null;
  port_range_min: number | null;
  port_range_max: number | null;
  remote_ip_prefix: string | null;
  remote_group_id: string | null;
  ethertype: string;
}

export interface SecurityGroup {
  id: string;
  name: string;
  description: string;
  rules: SecurityGroupRule[];
}

export interface Router {
  id: string;
  name: string;
  status: string;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

// ——— Router/Network 상세 도메인 ———

export interface RouterInterface {
  id: string;
  subnet_id: string;
  subnet_name: string;
  network_id: string;
  ip_address: string;
}

export interface RouterDetail {
  id: string;
  name: string;
  status: string;
  project_id: string | null;
  external_gateway_network_id: string | null;
  external_gateway_network_name: string | null;
  interfaces: RouterInterface[];
}

export interface SubnetDetail {
  id: string;
  name: string;
  cidr: string;
  network_id?: string;
  gateway_ip: string | null;
  dhcp_enabled: boolean;
}

export interface NetworkRouterInfo {
  id: string;
  name: string;
  status: string;
  project_id: string | null;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

export interface RouterListItem {
  id: string;
  name: string;
  status: string;
}

export interface NetworkDetail {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
  subnet_details: SubnetDetail[];
  routers: NetworkRouterInfo[];
}

export interface LoadBalancer {
  id: string;
  name: string;
  status: string;
  operating_status: string;
  vip_address: string | null;
  vip_subnet_id: string | null;
}

// 백엔드 기본 FloatingIp (항상 반환)
export interface FloatingIp {
  id: string;
  floating_ip_address: string;
  status: string;
  fixed_ip_address: string | null;
  port_id: string | null;
  instance_id?: string | null;
  instance_name?: string | null;
}

// topology 등 상세 컨텍스트용 (floating_network_id 포함)
export interface FloatingIpDetail extends FloatingIp {
  floating_network_id: string;
  project_id?: string | null;
}

// topology/types.ts와의 호환성을 위한 alias
export type FloatingIpInfo = FloatingIpDetail;

export interface KeypairInfo {
  name: string;
  fingerprint: string;
  type: string;
}

export interface FlavorInfo {
  id: string;
  name: string;
  vcpus: number;
  ram: number;
  disk: number;
  is_public?: boolean;
  extra_specs?: Record<string, string>;
  is_gpu?: boolean;
}

export interface ImageInfo {
  id: string;
  name: string;
  status: string;
  size?: number | null;
  min_disk?: number;
  min_ram?: number;
  disk_format?: string | null;
  container_format?: string | null;
  visibility?: string;
  owner?: string | null;
  tags?: string[];
  properties?: Record<string, string>;
  created_at?: string | null;
  updated_at?: string | null;
  is_protected?: boolean;
  os_type?: string | null;
  os_distro?: string | null;
}

export interface AvailabilityZone {
  name: string;
  state?: boolean;
}

export interface DashboardSummary {
  instances: { total: number; active: number; shutoff: number; error: number };
  compute: { instances_used: number; instances_limit: number; vcpus_used: number; vcpus_limit: number; ram_used_mb: number; ram_limit_mb: number };
  storage: { volumes_used: number; volumes_limit: number; gigabytes_used: number; gigabytes_limit: number };
  gpu_used: number;
}

// ——— Database 도메인 ———

export interface Datastore {
  type?: string;
  version?: string;
}

export interface DbInstance {
  id: string;
  name: string;
  status: string;
  datastore: Datastore;
  flavor_id: string;
  flavor_ram: number;
  flavor_vcpus: number;
  size: number;
  volume_used: number;
  created_at: string;
  updated_at: string;
  hostname: string;
  ip: string;
  ips: string[];
  address_map?: Record<string, string[]>;
}

export interface DbFlavor { id: string; name: string; ram: number; vcpus: number; disk: number; }
export interface DbDatabase { name: string; character_set: string; collate: string; }
export interface DbUser { name: string; host?: string; databases: { name: string }[]; }
export interface DbBackup {
  id: string;
  name: string;
  status: string;
  size: number;
  created_at: string;
  description: string;
  instance_id?: string;
}

export interface ImageDetail {
  id: string;
  name: string;
  status: string;
  size: number | null;
  min_disk: number;
  min_ram: number;
  disk_format: string | null;
  os_type: string | null;
  os_distro: string | null;
  created_at: string | null;
  owner: string | null;
  visibility: string | null;
  checksum: string | null;
  container_format: string | null;
  virtual_size: number | null;
  updated_at: string | null;
  protected: boolean;
  tags: string[];
  properties: Record<string, string>;
  os_hash_algo: string | null;
  os_hash_value: string | null;
  direct_url: string | null;
}

export interface ImageMember {
  member_id: string;
  status: string;
  created_at: string | null;
}

// ——— Volume 도메인 ———

export interface VolumeSnapshot {
  id: string;
  name: string;
  status: string;
  size: number;
  description: string;
  created_at: string | null;
}

// ——— K3s 도메인 ———

export interface K3sCluster {
  id: string;
  name: string;
  status: string;
  status_reason: string | null;
  server_vm_id: string | null;
  agent_vm_ids: string[];
  agent_count: number;
  api_address: string | null;
  server_ip: string | null;
  network_id: string | null;
  key_name: string | null;
  k3s_version: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface K3sNodeHealth {
  name: string;
  role: string;
  ready: boolean;
  conditions: string[];
  kubelet_version: string | null;
}

export interface K3sClusterHealth {
  cluster_id: string;
  cluster_name: string;
  status: string;
  api_server_reachable: boolean;
  healthz_ok: boolean;
  nodes: K3sNodeHealth[];
  checked_at: string;
  error: string | null;
  reachability: string;
}

// ——— LoadBalancer 도메인 ———

export interface LoadBalancerDetail {
  id: string;
  name: string;
  description: string;
  status: string;
  operating_status: string;
  vip_address: string | null;
  vip_subnet_id: string | null;
}

export interface Listener {
  id: string;
  name: string;
  protocol: string;
  protocol_port: number;
  status: string;
  default_pool_id: string | null;
}

export interface Pool {
  id: string;
  name: string;
  protocol: string;
  lb_algorithm: string;
  status: string;
}

export interface Member {
  id: string;
  name: string;
  address: string;
  protocol_port: number;
  weight: number;
  status: string;
}

export interface LbStatusNode {
  id: string;
  name: string;
  provisioning_status: string;
  operating_status: string;
  listeners?: LbStatusNode[];
  pools?: LbStatusNode[];
  members?: LbStatusNode[];
}

// ——— Container (Zun) 도메인 ———

export interface ZunContainer {
  uuid: string;
  name: string;
  status: string;
  status_reason: string | null;
  image: string | null;
  command: string | null;
  cpu: number | null;
  memory: string | null;
  created_at: string | null;
  addresses: Record<string, { addr: string }[]> | null;
  host: string | null;
}

// ——— Admin Volume 도메인 ———

export interface AdminVolumeAttachment {
  server_id: string;
  device: string;
  id: string;
}

export interface AdminVolumeDetail {
  id: string;
  name: string;
  status: string;
  size: number;
  volume_type: string;
  project_id: string | null;
  attachments: AdminVolumeAttachment[];
  created_at: string | null;
  description: string;
  bootable: boolean | null;
  encrypted: boolean | null;
  multiattach: boolean | null;
  metadata: Record<string, string>;
}
