import { get } from 'svelte/store';
import { ApiError } from '$lib/api/errors';
import { getMockupProfile, isMockAuthActive } from '$lib/stores/auth';
import { siteConfig } from '$lib/config/site';
import { buildMockAuth } from '$lib/mockup/auth';
import { MOCKUP_SESSION_KEY, MOCKUP_SERVICE_OVERRIDES, isMockupProfileId } from '$lib/mockup/contracts';
import type { MockupProfileId } from '$lib/mockup/contracts';
import { cloneMockup, getMockupState } from '$lib/mockup/state';
import type { K3sSseProgressMessage } from '$lib/api/k3sSseStream';

export const symbolNoMatch = Symbol('mockup-no-match');
const UNSUPPORTED = 'mockup mode에서는 이 작업을 아직 지원하지 않습니다.';
const MOCK_EXPIRES_AT_ISO = '2026-12-31T23:59:59Z';
function activeProfile(): MockupProfileId | null {
	if (typeof window !== 'undefined' && typeof window.location?.search === 'string') {
		const params = new URLSearchParams(window.location.search);
		const requested = params.get('mockup');
		if (params.has('mockup')) return isMockupProfileId(requested) ? requested : null;
	}
	if (!isMockAuthActive()) return null;
	const profile = getMockupProfile() ?? (
		typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(MOCKUP_SESSION_KEY)
	);
	return isMockupProfileId(profile) ? profile : null;
}

function normalizePath(path: string): string {
	const url = new URL(path, 'http://mockup.local');
	url.searchParams.delete('cache');
	url.searchParams.delete('refresh');
	const qs = url.searchParams.toString();
	return qs ? `${url.pathname}?${qs}` : url.pathname;
}

function ok204(): Record<string, never> {
	return {};
}

export function mockUnsupported(_message = UNSUPPORTED): never {
	throw new ApiError(409, UNSUPPORTED);
}

function updateInstanceStatus(id: string, status: string): void {
	const state = getMockupState();
	const target = state.instances.find((item) => item.id === id);
	if (target) target.status = status;
}

function deleteInstance(id: string): void {
	const state = getMockupState();
	state.instances = state.instances.filter((item) => item.id !== id);
	type TopologyWithMutableInstances = typeof state.topology & { instances: typeof state.topology.instances };
	const topology = state.topology as TopologyWithMutableInstances;
	topology.instances = topology.instances.filter((item) => item.id !== id);
}

function projectTokenResponse(projectId: string, profile: MockupProfileId): Record<string, unknown> {
	const state = getMockupState();
	const project = state.projects.find((item) => item.id === projectId) ?? state.projects[0];
	state.selectedProjectId = project.id;
	const admin = profile === 'admin';
	return {
		token: `mock-token-${admin ? 'admin' : 'tutorial'}-${project.id}`,
		refresh_token: `mock-refresh-${admin ? 'admin' : 'tutorial'}-${project.id}`,
		expires_at: MOCK_EXPIRES_AT_ISO,
		project_id: project.id,
		project_name: project.name,
		user_id: admin ? 'mock-admin-1' : 'mock-user-1',
		username: admin ? 'demo-admin' : 'demo-user',
		roles: admin ? ['admin'] : ['member'],
		is_system_admin: admin,
	};
}

function instanceMetrics(ids: string[]): Record<string, { cpu_avg: number | null; mem_avg: number | null; underutilized: boolean }> {
	const result: Record<string, { cpu_avg: number | null; mem_avg: number | null; underutilized: boolean }> = {};
	for (const [index, id] of ids.entries()) {
		result[id] = { cpu_avg: 8 + index * 7, mem_avg: 22 + index * 5, underutilized: index % 3 === 0 };
	}
	return result;
}

function metricSeries(scale: number): { ts: number; value: number }[] {
	return [0, 1, 2, 3, 4, 5].map((step) => ({ ts: 1783551600 + step * 600, value: scale + step * 3 }));
}

function dashboardTrend(range: string | null): Record<string, unknown> {
	return {
		vcpu: { data: [24, 27, 31, 29, 33, 36], points: 6, available: true },
		memory: { data: [38, 41, 44, 43, 45, 47], points: 6, available: true },
		storage: { data: [16, 18, 19, 20, 21, 23], points: 6, available: true },
		network: { data: [1.2, 1.5, 1.7, 1.4, 1.9, 2.1], points: 6, available: true, unit: 'Gbps' },
		prometheus_available: true,
		range: range ?? '14d',
	};
}

function routerDetail(id: string): Record<string, unknown> | null {
	const topology = getMockupState().topology;
	const router = topology.routers.find((item) => item.id === id);
	if (!router) return null;
	return {
		id: router.id,
		name: router.name,
		status: router.status,
		project_id: router.project_id,
		external_gateway_network_id: router.external_gateway_network_id,
		external_gateway_network_name: topology.networks.find((net) => net.id === router.external_gateway_network_id)?.name ?? null,
		interfaces: router.interface_ips.map((iface) => {
			const network = topology.networks.find((net) => net.subnet_details.some((subnet) => subnet.id === iface.subnet_id));
			const subnet = network?.subnet_details.find((item) => item.id === iface.subnet_id);
			return { id: `${router.id}-${iface.subnet_id}`, subnet_id: iface.subnet_id, subnet_name: subnet?.name ?? iface.subnet_id, network_id: network?.id ?? '', ip_address: iface.ip_address };
		}),
	};
}

function networkDetail(id: string): Record<string, unknown> | null {
	const topology = getMockupState().topology;
	const network = topology.networks.find((item) => item.id === id);
	if (!network) return null;
	return {
		...network,
		subnets: network.subnet_details.map((subnet) => subnet.id),
		routers: topology.routers.filter((router) => router.connected_subnet_ids.some((subnetId) => network.subnet_details.some((subnet) => subnet.id === subnetId))),
	};
}

function jsonFixture(method: string, normalized: string, body: unknown, profile: MockupProfileId): unknown | typeof symbolNoMatch {
	const state = getMockupState();
	const [pathname, query = ''] = normalized.split('?');
	const params = new URLSearchParams(query);

	if (method === 'GET' && pathname === '/api/v1/site-config') {
		return { ...get(siteConfig), services: { ...get(siteConfig).services, ...MOCKUP_SERVICE_OVERRIDES } };
	}
	if (method === 'GET' && pathname === '/api/v1/auth/me') {
		const auth = buildMockAuth(profile, profile === 'admin' ? '/admin' : '/dashboard');
		return { user_id: auth.userId, username: auth.username, project_id: auth.projectId, project_name: auth.projectName, roles: auth.roles, is_system_admin: auth.isSystemAdmin, auth_method: 'mockup' };
	}
	if (method === 'GET' && (pathname === '/api/v1/auth/projects/recent' || pathname === '/api/v1/auth/projects')) return state.projects;
	if (method === 'GET' && pathname === '/api/v1/profile') return { id: 'mock-user-1', name: 'Demo User', email: 'demo@example.com', default_project_id: null };
	if (method === 'POST' && pathname === '/api/v1/auth/token/project') return projectTokenResponse(String((body as { project_id?: string } | null)?.project_id ?? state.projects[0].id), profile);
	if (method === 'POST' && pathname === '/api/v1/networks/ensure-default') return ok204();

	if (method === 'GET' && pathname === '/api/v1/dashboard/summary') {
		return { instances: { total: state.instances.length, active: state.instances.filter((item) => item.status === 'ACTIVE').length, shutoff: state.instances.filter((item) => item.status === 'SHUTOFF').length, error: state.instances.filter((item) => item.status === 'ERROR').length }, gpu_used: state.instances.filter((item) => item.flavor_name?.startsWith('gpu.')).length };
	}
	if (method === 'GET' && pathname === '/api/v1/dashboard/quotas') return state.quotas;
	if (method === 'GET' && pathname === '/api/v1/dashboard/notifications') return { notifications: [{ type: 'quota', severity: 'warning', message: 'GPU quota 사용률이 70%를 넘었습니다.', count: 1 }, { type: 'backup', severity: 'info', message: '오늘 3개의 스냅샷 검증이 완료되었습니다.', count: 3 }] };
	if (method === 'GET' && pathname === '/api/v1/dashboard/metrics/trend') return dashboardTrend(params.get('range'));

	if (method === 'GET' && pathname === '/api/v1/instances') return state.instances;
	if (method === 'GET' && pathname === '/api/v1/instances/metrics-summary-batch') return { prometheus_available: true, instances: instanceMetrics(state.instances.map((item) => item.id)) };
	const instanceAction = pathname.match(/^\/api\/v1\/instances\/([^/]+)\/(start|stop|shelve|unshelve)$/);
	if (method === 'POST' && instanceAction) {
		const status = { start: 'ACTIVE', stop: 'SHUTOFF', shelve: 'SHELVED_OFFLOADED', unshelve: 'ACTIVE' }[instanceAction[2]] ?? 'ACTIVE';
		updateInstanceStatus(instanceAction[1], status);
		return ok204();
	}
	if (method === 'DELETE' && /^\/api\/v1\/instances\/[^/]+$/.test(pathname)) {
		deleteInstance(pathname.split('/').at(-1) ?? '');
		return ok204();
	}
	if (method === 'POST' && pathname === '/api/v1/instances/bulk-action') {
		const payload = body as { action?: string; instance_ids?: string[] } | null;
		for (const id of payload?.instance_ids ?? []) {
			if (payload?.action === 'delete') deleteInstance(id);
			else updateInstanceStatus(id, payload?.action === 'stop' ? 'SHUTOFF' : 'ACTIVE');
		}
		return { results: (payload?.instance_ids ?? []).map((id) => ({ id, ok: true })) };
	}
	const instanceId = pathname.match(/^\/api\/v1\/instances\/([^/]+)$/)?.[1];
	if (method === 'GET' && instanceId) return state.instances.find((item) => item.id === instanceId) ?? mockUnsupported();
	const metricInstanceId = pathname.match(/^\/api\/v1\/instances\/([^/]+)\/metrics-summary$/)?.[1];
	if (method === 'GET' && metricInstanceId) return { prometheus_available: true, stats: { cpu: { min: 4, avg: 18, max: 44 }, memory: { min: 18, avg: 36, max: 61 } }, recommendation: null };
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/metrics-batch$/.test(pathname)) {
		const keys = (params.get('metrics') ?? 'cpu,memory').split(',');
		return { metrics: Object.fromEntries(keys.map((key, index) => [key, { series: metricSeries(10 + index * 5), error: null }])) };
	}
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/console$/.test(pathname)) return { url: '/mockup-console.html' };
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/log$/.test(pathname)) return { output: 'cloud-init finished\nk3s service active\nmock workload healthy\n' };
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/interfaces$/.test(pathname)) return [{ id: 'mock-port-1', name: 'primary', status: 'ACTIVE', device_owner: 'compute:nova', fixed_ips: [{ ip_address: '192.0.2.24' }], project_id: state.selectedProjectId, security_group_ids: ['mock-sg-default'], mac_address: 'fa:16:3e:00:00:01', network_id: 'mock-net-private' }];
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/volumes$/.test(pathname)) return [{ id: 'mock-attachment-1', volume_id: 'mock-volume-1', server_id: 'mock-instance-1', device: '/dev/vda', name: 'root-disk', size: 80, status: 'in-use' }];
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/security-groups$/.test(pathname)) return { ports: [], security_groups: [{ id: 'mock-sg-default', name: 'default', description: 'Mock default SG', rules: [{ id: 'mock-rule-ssh', direction: 'ingress', protocol: 'tcp', port_range_min: 22, port_range_max: 22, remote_ip_prefix: '0.0.0.0/0', ethertype: 'IPv4' }] }] };
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/owner$/.test(pathname)) return { display: 'Sample Cloud Demo / demo-user' };
	if (method === 'GET' && /^\/api\/v1\/instances\/[^/]+\/storage-attachments$/.test(pathname)) return [{ file_storage_id: 'mock-share-1', name: 'demo-dataset', share_proto: 'CEPHFS', status: 'available' }];
	if (method === 'GET' && pathname === '/api/v1/storage/file-storages') return [{ id: 'mock-share-2', name: 'training-output', status: 'available', share_proto: 'CEPHFS' }];
	if (method === 'GET' && pathname === '/api/v1/volumes') return [{ id: 'mock-volume-2', name: 'scratch', status: 'available', size: 200, volume_type: 'ceph-ssd', attachments: [] }];

	if (method === 'GET' && pathname === '/api/v1/networks') return state.topology.networks.map((net) => ({ id: net.id, name: net.name, status: net.status, subnets: net.subnet_details.map((subnet) => subnet.id), is_external: net.is_external, is_shared: net.is_shared }));
	if (method === 'GET' && pathname === '/api/v1/networks/floating-ips') return state.topology.floating_ips;
	if (method === 'GET' && pathname === '/api/v1/networks/topology') return state.topology;
	if (method === 'GET' && pathname === '/api/v1/networks/topology/traffic') return state.traffic;
	const networkId = pathname.match(/^\/api\/v1\/networks\/([^/]+)$/)?.[1];
	if (method === 'GET' && networkId) return networkDetail(networkId) ?? mockUnsupported();
	if (method === 'GET' && pathname === '/api/v1/routers') return state.topology.routers.map((router) => ({ id: router.id, name: router.name, status: router.status, external_gateway_network_id: router.external_gateway_network_id, connected_subnet_ids: router.connected_subnet_ids }));
	const routerId = pathname.match(/^\/api\/v1\/routers\/([^/]+)$/)?.[1];
	if (method === 'GET' && routerId) return routerDetail(routerId) ?? mockUnsupported();

	if (method === 'GET' && pathname === '/api/v1/k3s/clusters') {
		const includeDeleted = params.get('include_deleted') === 'true';
		return state.k3sClusters.filter((cluster) => includeDeleted || !cluster.deleted_at);
	}
	const k3sClusterId = pathname.match(/^\/api\/v1\/k3s\/clusters\/([^/]+)$/)?.[1];
	if (method === 'GET' && k3sClusterId) return state.k3sClusters.find((cluster) => cluster.id === k3sClusterId) ?? mockUnsupported();
	if (method === 'GET' && pathname === '/api/v1/admin/k3s-clusters') return state.k3sClusters;
	const adminK3sClusterId = pathname.match(/^\/api\/v1\/admin\/k3s-clusters\/([^/]+)$/)?.[1];
	if (method === 'GET' && adminK3sClusterId) return state.k3sClusters.find((cluster) => cluster.id === adminK3sClusterId) ?? mockUnsupported();
	if (method === 'GET' && pathname === '/api/v1/k3s/cluster-templates') return [{ id: 'mock-template-1', name: 'GPU training baseline', description: '1 master + 2 workers', default_node_count: 2, default_agent_flavor_id: 'mock-flavor-cpu4', os_type: 'ubuntu' }];
	if (method === 'GET' && pathname === '/api/v1/flavors') return [{ id: 'mock-flavor-cpu4', name: 'cpu.4c_8g', vcpus: 4, ram: 8192, disk: 80 }, { id: 'mock-flavor-gpu', name: 'gpu.8c_64g_a10', vcpus: 8, ram: 65536, disk: 160, gpu_count: 1 }];
	if (method === 'GET' && pathname === '/api/v1/keypairs') return [{ name: 'demo-keypair' }];
	const healthClusterId = pathname.match(/^\/api\/v1\/k3s\/clusters\/([^/]+)\/health(?:\/check)?$/)?.[1];
	if ((method === 'GET' || (method === 'POST' && pathname.endsWith('/health/check'))) && healthClusterId) {
		const cluster = state.k3sClusters.find((item) => item.id === healthClusterId);
		if (!cluster) return mockUnsupported();
		return {
			cluster_id: cluster.id,
			cluster_name: cluster.name,
			status: cluster.status === 'ACTIVE' ? 'HEALTHY' : 'UNKNOWN',
			api_server_reachable: cluster.status === 'ACTIVE',
			healthz_ok: cluster.status === 'ACTIVE',
			nodes: [
				{ name: 'mock-server', role: 'server', ready: cluster.status === 'ACTIVE', conditions: cluster.status === 'ACTIVE' ? ['Ready'] : [], kubelet_version: 'v1.30.4+k3s1' },
				...cluster.agent_vm_ids.map((id, index) => ({ name: `mock-agent-${index + 1}`, role: 'agent', ready: cluster.status === 'ACTIVE', conditions: cluster.status === 'ACTIVE' ? ['Ready'] : [], kubelet_version: 'v1.30.4+k3s1' })),
			],
			checked_at: '2026-07-09T00:00:00Z',
			error: null,
			reachability: cluster.status === 'ACTIVE' ? 'direct' : 'unreachable',
		};
	}

	if (method === 'GET' && profile === 'admin' && pathname === '/api/v1/admin/overview') return state.admin.overview;
	if (method === 'GET' && profile === 'admin' && pathname === '/api/v1/admin/overview/projects') return state.admin.projects;
	if (method === 'GET' && profile === 'admin' && pathname === '/api/v1/admin/version') return state.admin.version;
	if (method === 'GET' && profile === 'admin' && pathname === '/api/v1/admin/notifications') return state.admin.notifications;
	if (method === 'GET' && profile === 'admin' && pathname === '/api/v1/admin/identity/summary') return state.admin.identitySummary;

	return symbolNoMatch;
}

export async function maybeMockJson<T>(method: string, path: string, body?: unknown, _token?: string, _projectId?: string): Promise<T | typeof symbolNoMatch> {
	const profile = activeProfile();
	if (!profile) return symbolNoMatch;
	const normalized = normalizePath(path);
	const upperMethod = method.toUpperCase();
	const fixture = jsonFixture(upperMethod, normalized, body, profile);
	if (fixture !== symbolNoMatch) return cloneMockup(fixture) as T;
	if (normalized.startsWith('/api/v1/') && upperMethod !== 'GET') mockUnsupported();
	if (normalized.startsWith('/api/v1/')) mockUnsupported();
	return symbolNoMatch;
}

export async function maybeMockBlob(method: string, path: string, _token?: string, _projectId?: string): Promise<Blob | typeof symbolNoMatch> {
	if (!activeProfile()) return symbolNoMatch;
	const normalized = normalizePath(path);
	if (method.toUpperCase() === 'GET' && /^\/api\/v1\/k3s\/clusters\/[^/]+\/kubeconfig$/.test(normalized)) {
		const content = 'apiVersion: v1\nkind: Config\nclusters:\n- name: afterglow-mockup\ncontexts:\n- name: afterglow-mockup\ncurrent-context: afterglow-mockup\n';
		const blob = new Blob([content], { type: 'application/x-yaml' }) as Blob & { text?: () => Promise<string> };
		blob.text ??= async () => content;
		return blob;
	}
	if (method.toUpperCase() === 'GET' && /^\/api\/v1\/k3s\/clusters\/[^/]+\/ca-certificate$/.test(normalized)) {
		const content = '-----BEGIN CERTIFICATE-----\nMIIBmockupCA\n-----END CERTIFICATE-----\n';
		const blob = new Blob([content], { type: 'application/x-pem-file' }) as Blob & { text?: () => Promise<string> };
		blob.text ??= async () => content;
		return blob;
	}
	if (normalized.startsWith('/api/v1/')) mockUnsupported();
	return symbolNoMatch;
}

export async function maybeMockHead(path: string, _token?: string, _projectId?: string): Promise<Response | typeof symbolNoMatch> {
	if (!activeProfile()) return symbolNoMatch;
	const normalized = normalizePath(path);
	if (/^\/api\/v1\/k3s\/clusters\/[^/]+\/kubeconfig$/.test(normalized)) return new Response(null, { status: 204 });
	if (normalized.startsWith('/api/v1/')) mockUnsupported();
	return symbolNoMatch;
}

async function* progress(messages: K3sSseProgressMessage[]): AsyncGenerator<K3sSseProgressMessage> {
	for (const message of messages) {
		yield message;
	}
}

export function maybeMockK3sStream(path: string, body: unknown, token?: string, projectId?: string): AsyncGenerator<K3sSseProgressMessage> | null {
	if (!activeProfile()) return null;
	const normalized = normalizePath(path);
	const state = getMockupState();
	if (normalized === '/api/v1/k3s/clusters/async') {
		const payload = body as { name?: string; agent_count?: number; network_id?: string; key_name?: string; master_count?: number } | null;
		const id = `mock-k3s-${state.k3sClusters.length + 1}`;
		state.k3sClusters.push({ id, name: payload?.name || 'mockup-new-cluster', status: 'ACTIVE', status_reason: null, server_vm_id: 'mock-instance-1', agent_vm_ids: [], agent_count: payload?.agent_count ?? 1, api_address: 'https://192.0.2.90:6443', server_ip: '192.0.2.90', network_id: payload?.network_id ?? 'mock-net-private', key_name: payload?.key_name ?? 'demo-keypair', k3s_version: 'v1.30.4+k3s1', created_at: '2026-07-09T00:10:00Z', updated_at: '2026-07-09T00:10:00Z', deleted_at: null, deleted_by_user_id: null, deleted_reason: null, master_count: payload?.master_count ?? 1 });
		return progress([
			{ step: 'create_vm', progress: 25, message: 'mock VM 생성 완료', cluster_id: id },
			{ step: 'install_k3s', progress: 70, message: 'mock k3s 설치 완료', cluster_id: id },
			{ step: 'completed', progress: 100, message: 'mock 클러스터 준비 완료', cluster_id: id },
		]);
	}
	const deleteMatch = normalized.match(/^\/api\/v1\/k3s\/clusters\/([^/]+)\/delete-async$/);
	if (deleteMatch) {
		const cluster = state.k3sClusters.find((item) => item.id === deleteMatch[1]);
		if (cluster) {
			cluster.status = 'DELETED';
			cluster.deleted_at = '2026-07-09T00:20:00Z';
			cluster.deleted_reason = 'mockup delete';
		}
		return progress([
			{ step: 'cordon', progress: 35, message: 'mock 노드 cordon 완료', cluster_id: deleteMatch[1] },
			{ step: 'delete', progress: 80, message: 'mock 리소스 정리 완료', cluster_id: deleteMatch[1] },
			{ step: 'completed', progress: 100, message: 'mock 클러스터 삭제 완료', cluster_id: deleteMatch[1] },
		]);
	}
	if (normalized.startsWith('/api/v1/')) mockUnsupported();
	return null;
}
