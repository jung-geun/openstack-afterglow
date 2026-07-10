import { describe, expect, it } from 'vitest';
import { getMockupState } from './state';

describe('mockup fixture privacy', () => {
	it('contains no production-looking identities or infrastructure values', () => {
		const serialized = JSON.stringify(getMockupState());
		const disclosedValues = [
			'dms-cloud',
			'DMS Lab',
			'gitlab-runner-2',
			'117.16.137.',
			'10.12.12.',
			'10.44.0.',
			'172.30.',
			'192.168.',
			'pieroot',
			'konkuk.ac.kr',
			'compute-03',
			'discord-bot',
		];

		for (const value of disclosedValues) {
			expect(serialized.toLowerCase()).not.toContain(value.toLowerCase());
		}
	});

	it('keeps private, data, and external fixture relationships internally consistent', () => {
		const state = getMockupState();
		const privateNetwork = state.topology.networks.find((network) => network.id === 'mock-net-private');
		const dataNetwork = state.topology.networks.find((network) => network.id === 'mock-net-data');
		const externalNetwork = state.topology.networks.find((network) => network.id === 'mock-net-public');

		expect(privateNetwork?.name).toBe('sample-private');
		expect(privateNetwork?.subnet_details[0]?.cidr).toBe('192.0.2.0/24');
		expect(dataNetwork?.subnet_details[0]?.cidr).toBe('198.51.100.0/24');
		expect(externalNetwork?.subnet_details[0]?.cidr).toBe('203.0.113.0/24');
		expect(state.instances.every((instance) => instance.ip_addresses.every((address) => address.type === 'floating'
		? address.addr.startsWith('203.0.113.')
		: address.addr.startsWith('192.0.2.')))).toBe(true);
		expect(state.k3sClusters.filter((cluster) => cluster.server_ip).every((cluster) => cluster.server_ip?.startsWith('192.0.2.'))).toBe(true);
		expect(state.topology.floating_ips.every((floatingIp) => floatingIp.floating_ip_address.startsWith('203.0.113.') && floatingIp.fixed_ip_address?.startsWith('192.0.2.'))).toBe(true);
		expect((state.topology.load_balancers ?? []).every((loadBalancer) => loadBalancer.vip_address?.startsWith('192.0.2.') && loadBalancer.vip_network_id === 'mock-net-private')).toBe(true);
	});
});
