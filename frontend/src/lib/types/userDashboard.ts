export interface InstanceItem {
	id: string;
	name: string;
	status: string;
	flavor_name: string;
	created_at: string;
}

export interface VolumeItem {
	id: string;
	name: string;
	status: string;
	size: number;
	volume_type: string;
	created_at: string;
}

export interface ProjectData {
	project_id: string;
	project_name: string;
	instances: InstanceItem[];
	volumes: VolumeItem[];
	instance_count: number;
	volume_count: number;
	storage_gb: number;
	vcpus: number;
	ram_mb: number;
	network_count: number;
	fip_count: number;
	error?: boolean;
}

export interface UserDashboardSummary {
	current_project_id: string;
	projects: ProjectData[];
	totals: {
		instances: number;
		volumes: number;
		storage_gb: number;
		vcpus: number;
		ram_mb: number;
		networks: number;
		floating_ips: number;
	};
}
