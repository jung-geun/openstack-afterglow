import type { Instance } from '$lib/types/compute';
import type { Volume } from '$lib/types/volume';
import type { DashboardQuotas } from '$lib/types/quotas';
import type { TopologyData, TopologyTraffic } from '$lib/types/topology';
import type { K3sCluster } from '$lib/types/k3s';
import type { Overview, ProjectUsage, VersionInfo } from '$lib/types/adminOverview';
import type { Project } from '$lib/stores/auth';

const NOW = '2026-07-09T00:00:00Z';
const PROJECT_ID = 'mock-project-1';

interface MockupState {
	projects: Project[];
	selectedProjectId: string;
	instances: Instance[];
	volumes: Volume[];
	k3sClusters: K3sCluster[];
	topology: TopologyData;
	traffic: TopologyTraffic;
	quotas: DashboardQuotas;
	admin: {
		overview: Overview;
		projects: ProjectUsage[];
		version: VersionInfo;
		notifications: { severity: string; message: string; target: string; href: string }[];
		identitySummary: {
			user_count: number;
			project_count: number;
			role_count: number;
			group_count: number;
			recent_users: { id: string; name: string }[];
			recent_projects: { id: string; name: string }[];
		};
	};
}

function instance(id: string, name: string, status: string, fixed: string, floating: string | null, flavor: string): Instance {
	return {
		id,
		name,
		status,
		image_name: 'Ubuntu 24.04 LTS',
		flavor_name: flavor,
		ip_addresses: [
			{ addr: fixed, type: 'fixed', network_name: 'sample-private' },
			...(floating ? [{ addr: floating, type: 'floating', network_name: 'sample-external' }] : []),
		],
		created_at: NOW,
		union_libraries: name.includes('sample-ci') ? ['sample-runner-tools'] : [],
		union_strategy: name.includes('sample-project') ? 'overlayfs' : null,
		metadata: { role: name.includes('sample-ci') ? 'ci' : 'sample' },
		image_id: 'fixture-image-ubuntu',
		flavor_id: `fixture-flavor-${flavor.replace(/[^a-z0-9]+/gi, '-')}`,
		key_name: 'sample-keypair',
		host: 'sample-hypervisor-a',
	};
}

function seedState(): MockupState {
	const instances = [
		instance('mock-instance-1', 'sample-project-alpha', 'ACTIVE', '192.0.2.24', '203.0.113.216', 'cpu.8c_32g'),
		instance('mock-instance-2', 'sample-project-beta', 'ACTIVE', '192.0.2.25', '203.0.113.221', 'cpu.4c_8g'),
		instance('mock-instance-3', 'sample-ci-runner', 'ACTIVE', '192.0.2.66', null, 'cpu.4c_16g'),
		instance('mock-instance-4', 'sample-ml-notebook', 'SHUTOFF', '192.0.2.41', null, 'gpu.8c_64g_a10'),
		instance('mock-instance-5', 'sample-api-check', 'SHELVED_OFFLOADED', '192.0.2.51', null, 'cpu.2c_4g'),
		instance('mock-instance-6', 'sample-batch-worker', 'ERROR', '192.0.2.67', null, 'cpu.4c_8g'),
		instance('mock-instance-7', 'sample-database', 'ACTIVE', '192.0.2.71', null, 'cpu.4c_16g'),
		instance('mock-instance-8', 'sample-observer', 'SHUTOFF', '192.0.2.72', '203.0.113.230', 'cpu.2c_4g'),
	];

	const networks = [
		{ id: 'mock-net-private', name: 'sample-private', status: 'ACTIVE', is_external: false, is_shared: false, project_id: PROJECT_ID, subnet_details: [{ id: 'mock-subnet-private', name: 'sample-private-subnet', cidr: '192.0.2.0/24', gateway_ip: '192.0.2.1', dhcp_enabled: true }] },
		{ id: 'mock-net-data', name: 'sample-data', status: 'ACTIVE', is_external: false, is_shared: true, project_id: PROJECT_ID, subnet_details: [{ id: 'mock-subnet-data', name: 'sample-data-subnet', cidr: '198.51.100.0/24', gateway_ip: '198.51.100.1', dhcp_enabled: true }] },
		{ id: 'mock-net-public', name: 'sample-external', status: 'ACTIVE', is_external: true, is_shared: true, project_id: null, subnet_details: [{ id: 'mock-subnet-public', name: 'sample-external-subnet', cidr: '203.0.113.0/24', gateway_ip: '203.0.113.1', dhcp_enabled: false }] },
	];

	const routers = [
		{ id: 'mock-router-main', name: 'sample-edge-router', status: 'ACTIVE', external_gateway_network_id: 'mock-net-public', external_gateway_ips: ['203.0.113.218'], interface_ips: [{ ip_address: '192.0.2.1', subnet_id: 'mock-subnet-private' }], is_distributed: true, is_ha: true, connected_subnet_ids: ['mock-subnet-private'], dvr_subnet_ids: [], project_id: PROJECT_ID },
		{ id: 'mock-router-data', name: 'sample-data-router', status: 'ACTIVE', external_gateway_network_id: null, external_gateway_ips: [], interface_ips: [{ ip_address: '198.51.100.1', subnet_id: 'mock-subnet-data' }], is_distributed: false, is_ha: false, connected_subnet_ids: ['mock-subnet-data'], dvr_subnet_ids: [], project_id: PROJECT_ID },
	];

	return {
		projects: [
			{ id: PROJECT_ID, name: 'sample-project-alpha', description: '튜토리얼 기본 프로젝트', domain_name: 'Sample Research Org', last_accessed_at: '2026-07-08T23:00:00Z' },
			{ id: 'mock-project-2', name: 'sample-project-beta', description: 'GPU 워크로드 데모', domain_name: 'Sample Research Org', last_accessed_at: '2026-07-08T12:30:00Z' },
			{ id: 'mock-project-3', name: 'sample-ci-runner', description: 'CI runner demo', domain_name: 'Sample Research Org', last_accessed_at: '2026-07-07T18:00:00Z' },
		],
		selectedProjectId: PROJECT_ID,
		instances,
		volumes: [
			{ id: 'mock-volume-1', name: 'root-disk', status: 'in-use', size: 80, volume_type: 'ceph-ssd', attachments: [{ server_id: 'mock-instance-1', device: '/dev/vda' }], bootable: true },
			{ id: 'mock-volume-2', name: 'scratch', status: 'available', size: 200, volume_type: 'ceph-ssd', attachments: [], bootable: false },
		],
		k3sClusters: [
			{ id: 'mock-k3s-1', name: 'sample-cluster-alpha', status: 'ACTIVE', status_reason: null, server_vm_id: 'mock-instance-1', agent_vm_ids: ['mock-instance-2', 'mock-instance-3'], agent_count: 2, api_address: 'https://192.0.2.24:6443', server_ip: '192.0.2.24', network_id: 'mock-net-private', key_name: 'sample-keypair', k3s_version: 'v1.30.4+k3s1', created_at: NOW, updated_at: NOW, deleted_at: null, deleted_by_user_id: null, deleted_reason: null, master_count: 1, stampede_enabled: true },
			{ id: 'mock-k3s-2', name: 'sample-cluster-pending', status: 'CREATE_IN_PROGRESS', status_reason: 'Installing sample agents', server_vm_id: 'mock-instance-4', agent_vm_ids: [], agent_count: 1, api_address: null, server_ip: '192.0.2.41', network_id: 'mock-net-private', key_name: 'sample-keypair', k3s_version: 'v1.30.4+k3s1', created_at: NOW, updated_at: NOW, deleted_at: null, deleted_by_user_id: null, deleted_reason: null, master_count: 1 },
			{ id: 'mock-k3s-3', name: 'sample-cluster-error', status: 'ERROR', status_reason: 'Sample agent bootstrap timed out', server_vm_id: 'mock-instance-6', agent_vm_ids: [], agent_count: 0, api_address: null, server_ip: '192.0.2.67', network_id: 'mock-net-private', key_name: 'sample-keypair', k3s_version: 'v1.29.8+k3s1', created_at: NOW, updated_at: NOW, deleted_at: null, deleted_by_user_id: null, deleted_reason: null, master_count: 1 },
		],
		topology: {
			networks,
			routers,
			instances: instances.slice(0, 4).map((i) => ({ id: i.id, name: i.name, status: i.status, project_id: PROJECT_ID, network_names: ['sample-private'], ip_addresses: i.ip_addresses })),
			floating_ips: [
				{ id: 'mock-fip-1', floating_ip_address: '203.0.113.216', status: 'ACTIVE', fixed_ip_address: '192.0.2.24', port_id: 'mock-port-1', instance_id: 'mock-instance-1', instance_name: 'sample-project-alpha', project_id: PROJECT_ID, router_id: 'mock-router-main', floating_network_id: 'mock-net-public' },
				{ id: 'mock-fip-2', floating_ip_address: '203.0.113.221', status: 'ACTIVE', fixed_ip_address: '192.0.2.25', port_id: 'mock-port-2', instance_id: 'mock-instance-2', instance_name: 'sample-project-beta', project_id: PROJECT_ID, router_id: 'mock-router-main', floating_network_id: 'mock-net-public' },
			],
			load_balancers: [{ id: 'mock-lb-1', name: 'sample-web-balancer', vip_address: '192.0.2.80', vip_port_id: 'mock-lb-port', vip_subnet_id: 'mock-subnet-private', vip_network_id: 'mock-net-private', provisioning_status: 'ACTIVE', operating_status: 'ONLINE', project_id: PROJECT_ID, listeners: [{ id: 'mock-listener-1', name: 'sample-https-listener', protocol: 'HTTPS', protocol_port: 443, default_pool_id: 'mock-pool-1' }], members: [{ id: 'mock-member-1', address: '192.0.2.24', protocol_port: 8443, status: 'ACTIVE', subnet_id: 'mock-subnet-private', pool_id: 'mock-pool-1', server_id: 'mock-instance-1' }] }],
		},
		traffic: {
			ts: 1783555200,
			instances: { 'mock-instance-1': { rx_bps: 2400000, tx_bps: 1800000 }, 'mock-instance-2': { rx_bps: 1200000, tx_bps: 900000 } },
			networks: { 'mock-net-private': { rx_bps: 5200000, tx_bps: 4300000 }, 'mock-net-data': { rx_bps: 800000, tx_bps: 600000 } },
			routers: { 'mock-router-main': { rx_bps: 4200000, tx_bps: 3900000 } },
			load_balancers: { 'mock-lb-1': { rx_bps: 1600000, tx_bps: 1500000 } },
		},
		quotas: {
			compute: { instances: { limit: 30, in_use: 8 }, cores: { limit: 128, in_use: 36 }, ram: { limit: 262144, in_use: 86016 } },
			storage: { volumes: { limit: 60, in_use: 14 }, gigabytes: { limit: 8000, in_use: 1250 } },
			network: { floatingip: { limit: 16, in_use: 3 } },
			file_storage: { shares: { limit: 12, in_use: 4 }, gigabytes: { limit: 4096, in_use: 780 } },
		},
		admin: {
			overview: { hypervisor_count: 7, running_vms: 46, gpu_instances: 8, instance_stats: { total: 58, active: 46, shutoff: 9, error: 3, other: 0 }, vcpus: { total: 768, allowed: 620, used: 312 }, ram_gb: { total: 2048, used: 890 }, disk_gb: { total: 78000, used: 31200 }, containers_count: 12, file_storage_count: 9, database_instances_count: 5, object_storage_containers_count: 18 },
			projects: [
				{ project_id: PROJECT_ID, project_name: 'sample-project-alpha', cpu: { used: 36, quota: 128 }, ram_mb: { used: 86016, quota: 262144 }, instances: { used: 8, quota: 30 }, disk_gb: { used: 1250, quota: 8000 }, gpu_instances: 1 },
				{ project_id: 'mock-project-2', project_name: 'sample-project-beta', cpu: { used: 72, quota: 160 }, ram_mb: { used: 196608, quota: 393216 }, instances: { used: 14, quota: 40 }, disk_gb: { used: 2600, quota: 12000 }, gpu_instances: 4 },
				{ project_id: 'mock-project-3', project_name: 'sample-ci-runner', cpu: { used: 24, quota: 80 }, ram_mb: { used: 49152, quota: 131072 }, instances: { used: 11, quota: 25 }, disk_gb: { used: 900, quota: 4000 }, gpu_instances: 0 },
				{ project_id: 'mock-project-4', project_name: 'sample-visual-research', cpu: { used: 96, quota: 192 }, ram_mb: { used: 262144, quota: 524288 }, instances: { used: 16, quota: 50 }, disk_gb: { used: 4200, quota: 16000 }, gpu_instances: 3 },
			],
			version: { platform: { backend_version: '0.0.0-mock' }, runtime: { python_version: '3.12.8', uptime_seconds: 864000 }, dependencies: { fastapi: '0.125.0', openstacksdk: '3.3.0' }, git: { commit: 'mockup', tag: 'v0.0.0-mock', branch: 'mockup' }, config: { k3s_version: 'v1.30.4+k3s1' } },
			notifications: [
				{ severity: 'critical', message: 'sample-compute-node-a GPU 온도가 임계치에 접근했습니다.', target: 'sample-compute-node-a', href: '/admin/monitoring' },
				{ severity: 'warning', message: 'sample-project-beta RAM quota 사용률 80% 초과', target: 'mock-project-2', href: '/admin/projects' },
				{ severity: 'info', message: '야간 백업 검증이 완료되었습니다.', target: 'sample-backup', href: '/admin/services' },
			],
			identitySummary: { user_count: 128, project_count: 24, role_count: 9, group_count: 14, recent_users: [{ id: 'mock-user-1', name: 'sample-user' }, { id: 'mock-user-2', name: 'sample-researcher' }], recent_projects: [{ id: PROJECT_ID, name: 'sample-project-alpha' }, { id: 'mock-project-4', name: 'sample-visual-research' }] },
		},
	};
}

let state = seedState();

export function resetMockupState(): void {
	state = seedState();
}

export function getMockupState(): MockupState {
	return state;
}

export function cloneMockup<T>(value: T): T {
	return structuredClone(value);
}
