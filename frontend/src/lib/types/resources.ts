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
}
