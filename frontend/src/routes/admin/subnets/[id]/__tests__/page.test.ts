import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import type { AdminSubnetDetail } from '$lib/types/networks';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('$app/stores', () => ({
	page: writable({ params: { id: 'sub-100' }, data: {} }),
}));

vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'admin-project' }),
}));

vi.mock('$lib/api/client', () => ({
	api: { get: mockGet },
	ApiError: class ApiError extends Error {
		status: number;
		constructor(message: string, status = 500) {
			super(message);
			this.status = status;
		}
	},
}));

import Page from '../+page.svelte';

const sampleSubnetDetail: AdminSubnetDetail = {
	id: 'sub-100',
	name: 'admin-subnet-primary',
	network_id: 'net-200',
	network_name: 'production-network',
	project_id: 'proj-admin-1',
	cidr: '10.200.0.0/24',
	gateway_ip: '10.200.0.1',
	ip_version: 4,
	dhcp_enabled: true,
	allocation_pools: [
		{ start: '10.200.0.10', end: '10.200.0.250' },
	],
	ports: [
		{
			id: 'port-1',
			name: 'web-port',
			status: 'ACTIVE',
			mac_address: 'fa:16:3e:11:22:33',
			device_owner: 'compute:nova',
			device_id: 'inst-1',
			project_id: 'proj-admin-1',
			ip_addresses: ['10.200.0.15'],
			binding_host_id: 'compute-node-01',
		},
	],
	allocations: [
		{
			ip_address: '10.200.0.15',
			port_id: 'port-1',
			port_name: 'web-port',
			device_owner: 'compute:nova',
			device_id: 'inst-1',
			project_id: 'proj-admin-1',
			binding_host_id: 'compute-node-01',
		},
	],
	dhcp_bindings: [
		{
			agent_id: 'agent-99',
			host: 'network-node-01',
			binary: 'neutron-dhcp-agent',
			availability_zone: 'nova',
			alive: true,
			admin_state_up: true,
			source: 'agent',
			ip_addresses: ['10.200.0.2'],
			port_ids: ['port-dhcp-1'],
		},
	],
	dhcp_agent_data_available: true,
};

describe('Admin Subnet Detail Page (/admin/subnets/[id])', () => {
	it('fetches and renders all requested subnet detail views completely', async () => {
		mockGet.mockResolvedValueOnce(sampleSubnetDetail);

		render(Page);

		expect(mockGet).toHaveBeenCalledWith('/api/v1/admin/subnets/sub-100', 'token', 'admin-project');

		// Summary & metadata
		expect(await screen.findByText('서브넷: admin-subnet-primary')).toBeTruthy();
		expect(screen.getByText('sub-100')).toBeTruthy();
		expect(screen.getAllByText('10.200.0.0/24').length).toBeGreaterThan(0);
		expect(screen.getByText('10.200.0.1')).toBeTruthy();
		expect(screen.getAllByText('IPv4').length).toBeGreaterThan(0);
		expect(screen.getByText('production-network')).toBeTruthy();

		// Navigation links
		const networkLinks = screen.getAllByRole('link', { name: /production-network|네트워크 상세/ });
		expect(networkLinks.some((el) => el.getAttribute('href') === '/admin/networks/net-200')).toBe(true);

		// Allocation pools
		expect(screen.getByText('10.200.0.10')).toBeTruthy();
		expect(screen.getByText('10.200.0.250')).toBeTruthy();

		// DHCP placement table
		expect(screen.getByText('network-node-01')).toBeTruthy();
		expect(screen.getByText('neutron-dhcp-agent')).toBeTruthy();
		expect(screen.getByText('agent-99')).toBeTruthy();
		expect(screen.getByText('10.200.0.2')).toBeTruthy();
		expect(screen.getByText('port-dhcp-1')).toBeTruthy();
		expect(screen.getByText('에이전트')).toBeTruthy();
		expect(screen.getByText('정상')).toBeTruthy();
		expect(screen.getByText('UP')).toBeTruthy();

		// Allocated IPs table
		expect(screen.getAllByText('10.200.0.15').length).toBeGreaterThan(0);
		expect(screen.getAllByText('port-1').length).toBeGreaterThan(0);
		expect(screen.getAllByText('compute:nova').length).toBeGreaterThan(0);
		expect(screen.getAllByText('inst-1').length).toBeGreaterThan(0);
		expect(screen.getAllByText('compute-node-01').length).toBeGreaterThan(0);

		// Port inventory is a separate tab.
		expect(screen.queryByText('web-port')).toBeNull();
		await fireEvent.click(screen.getByRole('button', { name: '포트 · 1' }));
		expect(screen.getByText('web-port')).toBeTruthy();
		expect(screen.getByText('ACTIVE')).toBeTruthy();
		expect(screen.getByText('fa:16:3e:11:22:33')).toBeTruthy();

		// Headers for actual binding node
		expect(screen.getAllByText(/실제 노드/).length).toBeGreaterThan(0);
	});

	it('renders warning alert and port-sourced DHCP rows when scheduler data is unavailable', async () => {
		const partialSubnet: AdminSubnetDetail = {
			...sampleSubnetDetail,
			dhcp_agent_data_available: false,
			dhcp_bindings: [
				{
					agent_id: null,
					host: 'ovn-chassis-02',
					binary: null,
					availability_zone: null,
					alive: null,
					admin_state_up: null,
					source: 'port',
					ip_addresses: ['10.200.0.3'],
					port_ids: ['port-ovn-dhcp'],
				},
			],
		};
		mockGet.mockResolvedValueOnce(partialSubnet);

		render(Page);

		expect(await screen.findByText('DHCP 에이전트 스케줄러 정보 미제공')).toBeTruthy();
		expect(screen.getByText('ovn-chassis-02')).toBeTruthy();
		expect(screen.getByText('포트')).toBeTruthy();
		expect(screen.getByText('10.200.0.3')).toBeTruthy();
		expect(screen.getByText('port-ovn-dhcp')).toBeTruthy();
	});

	it('renders empty state indicators when sections have no items', async () => {
		const emptySubnet: AdminSubnetDetail = {
			...sampleSubnetDetail,
			allocation_pools: [],
			ports: [],
			allocations: [],
			dhcp_bindings: [],
		};
		mockGet.mockResolvedValueOnce(emptySubnet);

		render(Page);

		expect(await screen.findByText('등록된 할당 풀이 없습니다')).toBeTruthy();
		expect(screen.getByText('DHCP 배치 정보가 없습니다')).toBeTruthy();
		expect(screen.getByText('할당된 IP가 없습니다')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: '포트 · 0' }));
		expect(screen.getByText('사용 중인 포트가 없습니다')).toBeTruthy();
	});

	it('paginates dense allocation tables at twenty rows', async () => {
		const allocations = Array.from({ length: 21 }, (_, index) => ({
			ip_address: `10.200.0.${index + 101}`,
			port_id: `port-${index + 101}`,
			port_name: `workload-port-${index + 101}`,
			device_owner: 'compute:nova',
			device_id: `instance-${index + 101}`,
			project_id: 'proj-admin-1',
			binding_host_id: `compute-${index + 1}`,
		}));
		mockGet.mockResolvedValueOnce({ ...sampleSubnetDetail, allocations });

		render(Page);

		expect(await screen.findByText('10.200.0.101')).toBeTruthy();
		expect(screen.getByText('10.200.0.120')).toBeTruthy();
		expect(screen.queryByText('10.200.0.121')).toBeNull();
		expect(screen.getByText('21개 중 1–20개')).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: '다음 →' }));
		expect(screen.getByText('10.200.0.121')).toBeTruthy();
		expect(screen.queryByText('10.200.0.101')).toBeNull();
		expect(screen.getByText('21개 중 21–21개')).toBeTruthy();
	});

	it('paginates the port tab independently', async () => {
		const ports = Array.from({ length: 21 }, (_, index) => ({
			id: `port-${index + 101}`,
			name: `workload-port-${index + 101}`,
			status: 'ACTIVE',
			mac_address: `fa:16:3e:00:00:${String(index + 1).padStart(2, '0')}`,
			device_owner: 'compute:nova',
			device_id: `instance-${index + 101}`,
			project_id: 'proj-admin-1',
			ip_addresses: [`10.200.0.${index + 101}`],
			binding_host_id: `compute-${index + 1}`,
		}));
		mockGet.mockResolvedValueOnce({ ...sampleSubnetDetail, ports });

		render(Page);
		await screen.findByText('서브넷: admin-subnet-primary');
		await fireEvent.click(screen.getByRole('button', { name: '포트 · 21' }));

		expect(screen.getByText('workload-port-101')).toBeTruthy();
		expect(screen.getByText('workload-port-120')).toBeTruthy();
		expect(screen.queryByText('workload-port-121')).toBeNull();

		await fireEvent.click(screen.getByRole('button', { name: '다음 →' }));
		expect(screen.getByText('workload-port-121')).toBeTruthy();
		expect(screen.queryByText('workload-port-101')).toBeNull();
	});

	it('renders error alert when API fetch fails', async () => {
		mockGet.mockRejectedValueOnce(new Error('네트워크 연결 오류'));

		render(Page);

		expect(await screen.findByText('서브넷 조회 실패')).toBeTruthy();
		expect(screen.getByText('네트워크 연결 오류')).toBeTruthy();
	});
});
