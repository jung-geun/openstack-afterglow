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
  union_upper_volume_id?: string | null;
  union_share_ids?: string[];
  metadata?: Record<string, string>;
  fault?: { code?: number; message?: string; details?: string; created?: string } | null;
  image_id?: string | null;
  flavor_id?: string | null;
  key_name?: string | null;
}

export interface DashboardSummary {
  instances: { total: number; active: number; shutoff: number; error: number };
  compute: { instances_used: number; instances_limit: number; vcpus_used: number; vcpus_limit: number; ram_used_mb: number; ram_limit_mb: number };
  storage: { volumes_used: number; volumes_limit: number; gigabytes_used: number; gigabytes_limit: number };
  gpu_used: number;
}

export interface ImageInfo {
  id: string;
  name: string;
  status: string;
  visibility?: string;
  size?: number;
  min_disk?: number;
  min_ram?: number;
  disk_format?: string;
  container_format?: string;
  created_at?: string;
  updated_at?: string;
  owner?: string;
  protected?: boolean;
  tags?: string[];
  os_distro?: string;
  os_type?: string;
}
