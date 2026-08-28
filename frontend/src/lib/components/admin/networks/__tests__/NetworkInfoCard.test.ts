import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { AdminNetworkDetail } from '$lib/types/networks';
import NetworkInfoCard from '../NetworkInfoCard.svelte';

const baseNetwork: AdminNetworkDetail = {
	id: 'net-1234-5678-90ab-cdef',
	name: 'admin-net',
	status: 'ACTIVE',
	subnets: ['sub-1', 'sub-2'],
	is_external: true,
	is_shared: false,
	subnet_details: [],
	routers: [],
	project_id: 'proj-1',
	provider_network_type: null,
	provider_segmentation_id: null,
	provider_physical_network: null,
};

describe('NetworkInfoCard', () => {
	it('renders basic network info and responsive grid contract', () => {
		const { container } = render(NetworkInfoCard, {
			props: { network: baseNetwork },
		});

		expect(screen.getByText('기본 정보')).toBeTruthy();
		expect(screen.getByText('네트워크 ID')).toBeTruthy();
		expect(screen.getByText('net-1234-5678-90ab-cdef')).toBeTruthy();
		expect(screen.getByText('서브넷 수')).toBeTruthy();
		expect(screen.getByText('2')).toBeTruthy();

		const dl = container.querySelector('dl');
		expect(dl).toBeTruthy();
		expect(dl?.className).toContain('grid-cols-1');
		expect(dl?.className).toContain('md:grid-cols-2');

		const idDd = screen.getByText('net-1234-5678-90ab-cdef');
		expect(idDd.className).toContain('break-all');
	});

	it('renders VLAN metadata with exact Korean labels, uppercased type, and physical network', () => {
		const vlanNetwork: AdminNetworkDetail = {
			...baseNetwork,
			provider_network_type: 'vlan',
			provider_segmentation_id: 100,
			provider_physical_network: 'physnet1',
		};

		render(NetworkInfoCard, {
			props: { network: vlanNetwork },
		});

		expect(screen.getByText('프로바이더 유형')).toBeTruthy();
		expect(screen.getByText('VLAN')).toBeTruthy();
		expect(screen.getByText('VLAN 태그')).toBeTruthy();
		expect(screen.getByText('100')).toBeTruthy();
		expect(screen.getByText('물리 네트워크')).toBeTruthy();
		expect(screen.getByText('physnet1')).toBeTruthy();
	});

	it('renders VXLAN metadata with exact Korean labels and omits physical network when null', () => {
		const vxlanNetwork: AdminNetworkDetail = {
			...baseNetwork,
			provider_network_type: 'vxlan',
			provider_segmentation_id: 5001,
			provider_physical_network: null,
		};

		render(NetworkInfoCard, {
			props: { network: vxlanNetwork },
		});

		expect(screen.getByText('프로바이더 유형')).toBeTruthy();
		expect(screen.getByText('VXLAN')).toBeTruthy();
		expect(screen.getByText('VXLAN VNI')).toBeTruthy();
		expect(screen.getByText('5001')).toBeTruthy();
		expect(screen.queryByText('물리 네트워크')).toBeNull();
	});

	it('renders em dash when segmentation ID is missing for VLAN or VXLAN', () => {
		const missingIdNetwork: AdminNetworkDetail = {
			...baseNetwork,
			provider_network_type: 'vlan',
			provider_segmentation_id: null,
			provider_physical_network: 'physnet2',
		};

		render(NetworkInfoCard, {
			props: { network: missingIdNetwork },
		});

		expect(screen.getByText('프로바이더 유형')).toBeTruthy();
		expect(screen.getByText('VLAN 태그')).toBeTruthy();
		expect(screen.getByText('—')).toBeTruthy();
	});

	it('omits provider metadata for flat/unrelated or absent provider type', () => {
		const flatNetwork: AdminNetworkDetail = {
			...baseNetwork,
			provider_network_type: 'flat',
			provider_segmentation_id: null,
			provider_physical_network: 'physnet1',
		};

		render(NetworkInfoCard, {
			props: { network: flatNetwork },
		});

		expect(screen.queryByText('프로바이더 유형')).toBeNull();
		expect(screen.queryByText('VLAN 태그')).toBeNull();
		expect(screen.queryByText('VXLAN VNI')).toBeNull();
		expect(screen.queryByText('물리 네트워크')).toBeNull();
	});
});
