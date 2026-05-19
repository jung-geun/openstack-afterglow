export interface Service {
  id: string;
  binary: string;
  host: string;
  status: string;
  state: string;
  zone: string;
  updated_at: string | null;
  disabled_reason: string | null;
}

export interface NetworkAgent {
  id: string;
  binary: string;
  host: string;
  agent_type: string;
  availability_zone: string | null;
  alive: boolean | null;
  admin_state_up: boolean;
  updated_at: string | null;
}

export interface EndpointGroup {
  service_id: string;
  name: string;
  service: string;
  region: string;
  endpoints: Record<string, string>;
}

export interface StoragePool {
  name: string;
  volume_backend_name: string;
  driver_version: string;
  storage_protocol: string;
  vendor_name: string;
  total_capacity_gb: number;
  free_capacity_gb: number;
  allocated_capacity_gb: number;
}

export type TabKey =
  | 'compute'
  | 'network'
  | 'block_storage'
  | 'shared_file_system'
  | 'orchestration'
  | 'container'
  | 'container_infra'
  | 'endpoints'
  | 'storage_pools';
