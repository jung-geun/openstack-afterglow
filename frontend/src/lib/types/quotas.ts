export interface Project { id: string; name: string; }
export interface QuotaLimit { limit: number; in_use: number; }
export interface Quotas {
	compute?: { instances?: QuotaLimit; cores?: QuotaLimit; ram?: QuotaLimit };
	volume?: { volumes?: QuotaLimit; gigabytes?: QuotaLimit };
}
export interface GpuQuota { gpu_type: string; limit: number; in_use: number; available: number; }
export interface GpuDefaultQuota { gpu_type: string; limit: number; }
