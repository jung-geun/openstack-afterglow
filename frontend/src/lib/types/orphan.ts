export interface OrphanFipInfo {
	id: string;
	address: string;
	project_id: string | null;
	created_at: string | null;
	age_days: number;
}
export interface OrphanVolumeInfo {
	id: string;
	name: string | null;
	size_gb: number;
	project_id: string | null;
	status: string;
	created_at: string | null;
	age_days: number;
}
export interface OrphanShareInfo {
	id: string;
	name: string | null;
	size_gb: number;
	project_id: string | null;
	status: string;
	created_at: string | null;
	age_days: number;
	snapshot_count: number;
}
export interface OrphanSecurityGroupInfo {
	id: string;
	name: string;
	description: string | null;
	project_id: string | null;
	created_at: string | null;
	age_days: number;
}
export interface OrphanScanResponse {
	floating_ips: OrphanFipInfo[];
	volumes: OrphanVolumeInfo[];
	manila_shares: OrphanShareInfo[];
	security_groups: OrphanSecurityGroupInfo[];
}
export interface CleanupResult {
	deleted: string[];
	failed: { id: string; error: string }[];
}
export type OrphanKind = 'floating_ip' | 'volume' | 'manila_share' | 'security_group';
