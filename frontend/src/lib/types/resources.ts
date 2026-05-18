export interface IpAddress {
  addr: string;
  type: string;
  network_name: string;
}

export interface Instance {
  id: string;
  name: string;
  status: string;
  image_name: string | null;
  flavor_name: string | null;
  ip_addresses: IpAddress[];
  created_at: string | null;
  union_libraries: string[];
  union_strategy: string | null;
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

export interface Network {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
}

export interface Router {
  id: string;
  name: string;
  status: string;
  external_gateway_network_id: string | null;
  connected_subnet_ids: string[];
}

export interface LoadBalancer {
  id: string;
  name: string;
  status: string;
  operating_status: string;
  vip_address: string | null;
  vip_subnet_id: string | null;
}

export interface LoadBalancerDetail {
  id: string;
  name: string;
  description?: string | null;
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
  address: string;
  protocol_port: number;
  weight: number;
  status: string;
}

export interface LbStatusNode {
  provisioning_status?: string | null;
  operating_status?: string | null;
  listeners?: Array<{
    id?: string;
    name?: string;
    provisioning_status?: string;
    pools?: Array<{
      id?: string;
      name?: string;
      provisioning_status?: string;
      members?: Array<{
        id?: string;
        name?: string;
        provisioning_status?: string;
      }>;
    }>;
  }>;
  pools?: Array<{
    id?: string;
    name?: string;
    provisioning_status?: string;
  }>;
}

export interface DashboardSummary {
  instances: { total: number; active: number; shutoff: number; error: number };
  compute: { instances_used: number; instances_limit: number; vcpus_used: number; vcpus_limit: number; ram_used_mb: number; ram_limit_mb: number };
  storage: { volumes_used: number; volumes_limit: number; gigabytes_used: number; gigabytes_limit: number };
  gpu_used: number;
}

export interface FloatingIp {
  id: string;
  floating_ip_address: string;
  status: string;
  fixed_ip_address: string | null;
  port_id: string | null;
  instance_id?: string | null;
  instance_name?: string | null;
}

export interface DbInstance {
  id: string;
  name: string;
  status: string;
  datastore: { type?: string; version?: string };
  flavor_id: string;
  flavor_ram: number;
  size: number;
  created_at: string;
  hostname: string;
  ip: string;
}

export interface DbDatabase {
  name: string;
  character_set: string;
  collate: string;
}

export interface DbUser {
  name: string;
  databases: { name: string }[];
}

export interface DbBackup {
  id: string;
  name: string;
  status: string;
  size: number;
  created_at: string;
}

export interface AdminVolumeDetail {
  id: string;
  name: string;
  status: string;
  size: number;
  volume_type: string;
  project_id: string | null;
  attachments: { server_id: string; device: string; id: string }[];
  created_at: string | null;
  description: string;
  bootable: boolean | null;
  encrypted: boolean | null;
  multiattach: boolean | null;
  metadata: Record<string, string>;
}

export interface SecurityGroup {
  id: string;
  name: string;
  description: string;
  rules: {
    id: string;
    direction: string;
    protocol: string | null;
    port_range_min: number | null;
    port_range_max: number | null;
    remote_ip_prefix: string | null;
    ethertype: string;
  }[];
}

export interface QuotaItem {
  limit: number;
  in_use: number;
}

export interface Quotas {
  compute: { instances: QuotaItem; cores: QuotaItem; ram: QuotaItem; };
  storage: { volumes: QuotaItem; gigabytes: QuotaItem; };
  network: { floatingip: QuotaItem; };
  file_storage: { shares: QuotaItem; gigabytes: QuotaItem; };
}

export interface VolumeBackup {
  id: string;
  name: string;
  description: string | null;
  volume_id: string;
  status: string;
  size: number;
  created_at: string | null;
  is_incremental: boolean;
  has_dependent_backups: boolean;
}

export interface SwiftContainer {
  name: string;
  count: number;
  bytes: number;
  project_id?: string;
  project_name?: string;
  is_quarantine?: boolean;
}

export interface Snapshot {
  id: string;
  name: string;
  status: string;
  volume_id: string;
  size: number;
  description: string;
  created_at: string | null;
}

export interface AdminVolume {
  id: string;
  name: string;
  status: string;
  size: number;
  project_id: string | null;
  created_at: string | null;
  bootable?: boolean;
  project_name?: string;
}

export interface PagedResponse<T> {
  items: T[];
  next_marker: string | null;
  count: number;
}

export interface TsPoint {
  ts: number;
  [key: string]: number | undefined;
}

export interface AdminNetwork {
  id: string;
  name: string;
  status: string;
  subnets: string[];
  is_external: boolean;
  is_shared: boolean;
  project_id?: string | null;
  project_name?: string;
}
