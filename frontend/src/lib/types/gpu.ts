export interface GpuDevice {
	provider_name: string;
	provider_uuid: string;
	pci_address: string;
	resource_class: string;
	vendor_id: string;
	vendor_name: string;
	device_id: string;
	device_name: string;
	total: number;
	used: number;
	allocation_ratio: number;
	reserved: number;
}

export interface GpuHost {
	name: string;
	uuid: string;
	gpus: GpuDevice[];
	gpu_total: number;
	gpu_used: number;
}

export interface GpuGroup {
	device_name: string;
	vendor_name: string;
	total: number;
	used: number;
}

export interface AggregatedHost {
	name: string;
	gpus: GpuDevice[];
	gpu_groups: GpuGroup[];
	gpu_total: number;
	gpu_used: number;
}

export interface GpuType {
	device_name: string;
	vendor: string;
	total: number;
	used: number;
}

export interface GpuCatalogDevice {
	vendor_id: string;
	device_id: string;
	vendor_name: string;
	name: string;
	is_audio: boolean;
	aliases: string[];
	source: 'builtin' | 'config' | 'db';
}

export interface GpuResponse {
	hosts: GpuHost[];
	aggregated_hosts: AggregatedHost[];
	summary: {
		total_hosts: number;
		total_gpus: number;
		used_gpus: number;
		available_gpus: number;
	};
	gpu_types: GpuType[];
}
