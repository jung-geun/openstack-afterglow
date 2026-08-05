import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import MonitoringSummaryTab, { type MonitoringSummary } from './MonitoringSummaryTab.svelte';

const summary: MonitoringSummary = {
	compute: {
		hypervisors_total: 1,
		hypervisors_up: 1,
		vcpus_used: 2,
		vcpus_total: 4,
		memory_used_mb: 1024,
		memory_total_mb: 2048,
		running_vms: 1,
		gpu_instances: 0,
		instance_stats: { total: 1, active: 1, shutoff: 0, error: 0, other: 0 },
	},
	storage: {
		volume_count: 0,
		volume_by_status: {},
		total_gb: 0,
		file_storage_count: 0,
	},
	network: {
		network_count: 0,
		router_count: 0,
		router_active: 0,
		floatingip_count: 0,
		floatingip_active: 0,
		port_count: 0,
	},
	containers: {
		zun_count: 0,
		k3s_count: 0,
		k3s_active: 0,
		k3s_available: false,
	},
};

describe('MonitoringSummaryTab', () => {
	it('labels unavailable Drover inventory instead of showing a misleading zero', () => {
		render(MonitoringSummaryTab, { props: { summary, loading: false, refreshing: false } });

		expect(screen.getByText('사용할 수 없음')).toBeTruthy();
	});
});
