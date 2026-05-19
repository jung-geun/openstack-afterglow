export interface Project { id: string; name: string; }
export interface QuotaLimit { limit: number; in_use: number; }
export interface Quotas {
	compute?: { instances?: QuotaLimit; cores?: QuotaLimit; ram?: QuotaLimit };
	volume?: { volumes?: QuotaLimit; gigabytes?: QuotaLimit };
}
export interface GpuQuota { gpu_type: string; limit: number; in_use: number; available: number; }
export interface GpuDefaultQuota { gpu_type: string; limit: number; }
export interface QuotaItem { limit: number; in_use: number; }
export interface ManilaFileQuota { shares: QuotaItem; gigabytes: QuotaItem; share_networks: QuotaItem; }

export interface DashboardQuotas {
  compute: { instances: QuotaItem; cores: QuotaItem; ram: QuotaItem; };
  storage: { volumes: QuotaItem; gigabytes: QuotaItem; };
  network: { floatingip: QuotaItem; };
  file_storage: { shares: QuotaItem; gigabytes: QuotaItem; };
}
