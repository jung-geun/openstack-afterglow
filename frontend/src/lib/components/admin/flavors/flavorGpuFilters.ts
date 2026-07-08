import type { Flavor } from '$lib/types/flavor';

export type GpuFilterValue = string;

export interface GpuFilterOption {
	value: GpuFilterValue;
	label: string;
}

export const GPU_FILTER_ALL = '';
export const GPU_FILTER_HAS_GPU = '__gpu__';
export const GPU_FILTER_NO_GPU = '__non_gpu__';

const BASE_GPU_OPTIONS: GpuFilterOption[] = [
	{ value: GPU_FILTER_ALL, label: 'GPU 전체' },
	{ value: GPU_FILTER_HAS_GPU, label: 'GPU 있음' },
	{ value: GPU_FILTER_NO_GPU, label: 'GPU 없음' },
];

export function normalizeGpuAlias(value: string): string {
	return value.replace(/[\s_.-]+/g, '').toLowerCase();
}

export function parseGpuAliasSpecs(extraSpecs: Record<string, string> | undefined): string[] {
	const aliasSpec = extraSpecs?.['pci_passthrough:alias'] ?? '';
	if (!aliasSpec) return [];

	return aliasSpec
		.split(',')
		.map((entry) => entry.trim())
		.filter((entry) => entry.includes(':') && !entry.toLowerCase().includes('audio'))
		.map((entry) => entry.slice(0, entry.lastIndexOf(':')).trim())
		.filter(Boolean);
}

export function buildGpuFilterOptions(flavors: Flavor[]): GpuFilterOption[] {
	const aliasesByNormalized = new Map<string, string>();
	for (const flavor of flavors) {
		for (const alias of parseGpuAliasSpecs(flavor.extra_specs)) {
			const normalized = normalizeGpuAlias(alias);
			if (normalized && !aliasesByNormalized.has(normalized)) {
				aliasesByNormalized.set(normalized, alias);
			}
		}
	}

	const aliasOptions = [...aliasesByNormalized.values()]
		.sort((a, b) => a.localeCompare(b))
		.map((alias) => ({ value: alias, label: alias }));

	return [...BASE_GPU_OPTIONS, ...aliasOptions];
}

export function matchesGpuFilter(flavor: Flavor, filter: GpuFilterValue): boolean {
	if (filter === GPU_FILTER_ALL) return true;
	if (filter === GPU_FILTER_HAS_GPU) return flavor.is_gpu;
	if (filter === GPU_FILTER_NO_GPU) return !flavor.is_gpu;

	const normalizedFilter = normalizeGpuAlias(filter);
	return parseGpuAliasSpecs(flavor.extra_specs).some(
		(alias) => normalizeGpuAlias(alias) === normalizedFilter,
	);
}
