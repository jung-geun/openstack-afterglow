export interface Overview {
	hypervisor_count: number;
	running_vms: number;
	gpu_instances: number;
	instance_stats?: { total: number; active: number; shutoff: number; error: number; other: number };
	vcpus: { total: number; allowed: number; used: number };
	ram_gb: { total: number; used: number };
	disk_gb: { total: number; used: number };
	containers_count: number;
	file_storage_count: number;
	database_instances_count: number;
	object_storage_containers_count: number;
}

export interface VersionInfo {
	platform: { backend_version: string };
	runtime: { python_version: string; uptime_seconds: number };
	dependencies: Record<string, string | null>;
	git: { commit: string | null; tag: string | null; branch: string | null };
}

export interface ProjectUsage {
	project_id: string;
	project_name: string;
	cpu: { used: number; quota: number };
	ram_mb: { used: number; quota: number };
	instances: { used: number; quota: number };
	disk_gb: { used: number; quota: number };
	gpu_instances: number;
}
