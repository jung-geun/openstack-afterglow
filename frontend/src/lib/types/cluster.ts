export interface Cluster {
  id: string;
  name: string;
  status: string;
  status_reason: string | null;
  cluster_template_id: string | null;
  master_count: number;
  node_count: number;
  api_address: string | null;
  coe_version: string | null;
  keypair: string | null;
  create_timeout: number | null;
  created_at: string | null;
  updated_at: string | null;
  stack_id: string | null;
}

export interface ClusterTemplate {
  id: string;
  name: string;
  coe: string;
}

export interface CreateClusterForm {
  name: string;
  cluster_template_id: string;
  node_count: number;
  master_count: number;
  keypair: string;
}

export interface StackResource {
  resource_name: string;
  resource_type: string;
  physical_resource_id: string;
  resource_status: string;
  resource_status_reason: string | null;
  created_at: string | null;
}

export interface StackEvent {
  resource_name: string;
  resource_status: string;
  resource_status_reason: string | null;
  event_time: string;
  logical_resource_id: string | null;
  physical_resource_id: string | null;
}

export const clusterStatusColor: Record<string, string> = {
  CREATE_COMPLETE:    'text-green-400 bg-green-900/30',
  CREATE_IN_PROGRESS: 'text-yellow-400 bg-yellow-900/30',
  CREATE_FAILED:      'text-red-400 bg-red-900/30',
  UPDATE_IN_PROGRESS: 'text-blue-400 bg-blue-900/30',
  UPDATE_COMPLETE:    'text-green-400 bg-green-900/30',
  DELETE_IN_PROGRESS: 'text-orange-400 bg-orange-900/30',
  DELETE_FAILED:      'text-red-400 bg-red-900/30',
};

export function resourceStatusColor(s: string): string {
  if (s.endsWith('_COMPLETE')) return 'text-green-400';
  if (s.endsWith('_IN_PROGRESS')) return 'text-yellow-400';
  if (s.endsWith('_FAILED')) return 'text-red-400';
  return 'text-gray-400';
}
