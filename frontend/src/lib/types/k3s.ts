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
	deleted_at: string | null;
	deleted_by_user_id: string | null;
	deleted_reason: string | null;
}
export interface K3sFlavor { id: string; name: string; vcpus: number; ram: number; disk: number; }
export interface K3sNetwork { id: string; name: string; is_external: boolean; }
export interface K3sKeypair { name: string; }

export interface K3sClusterTemplate {
	id: string;
	name: string;
	description: string | null;
	k3s_version: string | null;
	default_node_count: number;
	default_agent_flavor_id: string | null;
	default_image_id: string | null;
	plugins_enabled: Record<string, boolean>;
	os_type: string;
	public_visible: boolean;
	created_by: string | null;
	created_at: string | null;
	updated_at: string | null;
}
