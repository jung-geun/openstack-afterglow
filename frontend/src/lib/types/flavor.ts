export interface Flavor {
	id: string;
	name: string;
	vcpus: number;
	ram: number;
	disk: number;
	is_public: boolean;
	description: string | null;
	extra_specs: Record<string, string>;
	is_gpu: boolean;
	gpu_count: number;
}

export interface PagedResponse<T> {
	items: T[];
	next_marker: string | null;
	count: number;
}
