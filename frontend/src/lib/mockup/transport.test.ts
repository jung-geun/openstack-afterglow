import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MOCKUP_SESSION_KEY } from '$lib/mockup/contracts';
import type { K3sSseProgressMessage } from '$lib/api/k3sSseStream';
import type { K3sCluster } from '$lib/types/k3s';
let fetchMock = vi.fn();

beforeEach(() => {
	vi.resetModules();
	fetchMock = vi.fn(() => {
		throw new Error('mockup transport tests must stay network-free');
	});
	vi.stubGlobal('fetch', fetchMock);
	localStorage.clear();
	sessionStorage.clear();
	sessionStorage.setItem(MOCKUP_SESSION_KEY, 'on');
});

afterEach(() => {
	window.history.replaceState({}, '', '/');
	vi.unstubAllGlobals();
});

describe('mockup transport', () => {
	it('serves supported JSON reads and applies local instance mutations to later GETs', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockJson } = await import('./transport');
		const instancesBefore = (await maybeMockJson<Array<{ id: string; status: string }>>(
			'GET',
			'/api/v1/instances',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Array<{ id: string; status: string }>;
		const stopped = instancesBefore.find((instance) => instance.status === 'SHUTOFF');

		expect(stopped).toBeTruthy();

		await maybeMockJson(
			'POST',
			`/api/v1/instances/${stopped!.id}/start`,
			{},
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const instancesAfter = (await maybeMockJson<Array<{ id: string; status: string }>>(
			'GET',
			'/api/v1/instances',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Array<{ id: string; status: string }>;

		expect(instancesAfter.find((instance) => instance.id === stopped!.id)?.status).toBe('ACTIVE');
		const consoleTarget = (await maybeMockJson<{ url: string }>(
			'GET',
			`/api/v1/instances/${stopped!.id}/console`,
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as { url: string };

		expect(consoleTarget).toEqual({ url: '/mockup-console.html' });
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('streams fake k3s progress and exposes the created cluster on subsequent reads', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockJson, maybeMockK3sStream } = await import('./transport');
		const clustersBefore = (await maybeMockJson<K3sCluster[]>(
			'GET',
			'/api/v1/k3s/clusters',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as K3sCluster[];
		const progress = maybeMockK3sStream(
			'/api/v1/k3s/clusters/async',
			{ name: 'tutorial-created-cluster', agent_count: 2, os_type: 'ubuntu' },
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const messages: K3sSseProgressMessage[] = [];

		expect(progress).not.toBeNull();

		for await (const message of progress!) {
			messages.push(message);
		}

		expect(messages.length).toBeGreaterThan(0);
		expect(messages.at(-1)).toMatchObject({ step: 'completed' });

		const clustersAfter = (await maybeMockJson<K3sCluster[]>(
			'GET',
			'/api/v1/k3s/clusters',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as K3sCluster[];

		expect(clustersAfter).toHaveLength(clustersBefore.length + 1);
		expect(clustersAfter.some((cluster) => cluster.name === 'tutorial-created-cluster')).toBe(true);
	});

	it('serves K3s detail and health contracts, including deleted clusters on request', async () => {
		// Dynamic import reinitializes the mutable mock fixture with the session-scoped profile.
		const { maybeMockJson, maybeMockK3sStream } = await import('./transport');
		const clusters = (await maybeMockJson<K3sCluster[]>('GET', '/api/v1/k3s/clusters')) as K3sCluster[];
		const active = clusters.find((cluster) => cluster.status === 'ACTIVE');

		expect(active).toBeTruthy();
		const detail = await maybeMockJson<K3sCluster>('GET', `/api/v1/k3s/clusters/${active!.id}`);
		const health = (await maybeMockJson<{
			status: string;
			api_server_reachable: boolean;
			healthz_ok: boolean;
			nodes: { ready: boolean; kubelet_version: string | null }[];
			error: string | null;
		}>('GET', `/api/v1/k3s/clusters/${active!.id}/health`)) as {
			status: string;
			api_server_reachable: boolean;
			healthz_ok: boolean;
			nodes: { ready: boolean; kubelet_version: string | null }[];
			error: string | null;
		};

		expect(detail).toMatchObject({ id: active!.id, status: 'ACTIVE' });
		expect(health).toMatchObject({
			status: 'HEALTHY',
			api_server_reachable: true,
			healthz_ok: true,
			error: null,
		});
		expect(health.nodes).toEqual(expect.arrayContaining([expect.objectContaining({ ready: true, kubelet_version: 'v1.30.4+k3s1' })]));

		const deletion = maybeMockK3sStream(`/api/v1/k3s/clusters/${active!.id}/delete-async`, {}, undefined, undefined);
		expect(deletion).not.toBeNull();
		const current = (await maybeMockJson<K3sCluster[]>('GET', '/api/v1/k3s/clusters')) as K3sCluster[];
		const withDeleted = (await maybeMockJson<K3sCluster[]>('GET', '/api/v1/k3s/clusters?include_deleted=true')) as K3sCluster[];

		expect(current.some((cluster) => cluster.id === active!.id)).toBe(false);
		expect(withDeleted).toContainEqual(expect.objectContaining({ id: active!.id, status: 'DELETED' }));
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('keeps administrator privileges when an admin mock changes project', async () => {
		sessionStorage.clear();
		sessionStorage.setItem(MOCKUP_SESSION_KEY, 'admin');
		vi.resetModules();
		// Dynamic import reloads auth and transport against the administrator tab fixture.
		const { maybeMockJson } = await import('./transport');
		const token = await maybeMockJson<{
			is_system_admin: boolean;
			roles: string[];
		}>('POST', '/api/v1/auth/token/project', { project_id: 'mock-project-2' });

		expect(token).toMatchObject({ is_system_admin: true, roles: ['admin'] });
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('intercepts a query-activated mock before auth hydration can reach fetch', async () => {
		sessionStorage.clear();
		window.history.replaceState({}, '', '/dashboard?tutorial=on');
		vi.resetModules();
		// Dynamic import proves query bootstrap works before auth has a stored mock snapshot.
		const { maybeMockJson } = await import('./transport');
		const instances = await maybeMockJson<Array<{ id: string }>>('GET', '/api/v1/instances');

		expect(instances).toEqual(expect.arrayContaining([expect.objectContaining({ id: 'mock-instance-1' })]));
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('serves kubeconfig availability through HEAD and blob handlers for active clusters', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockBlob, maybeMockHead, maybeMockJson } = await import('./transport');
		const clusters = (await maybeMockJson<K3sCluster[]>(
			'GET',
			'/api/v1/k3s/clusters',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as K3sCluster[];
		const activeCluster = clusters.find((cluster) => cluster.status === 'ACTIVE');

		expect(activeCluster).toBeTruthy();

		const head = (await maybeMockHead(
			`/api/v1/k3s/clusters/${activeCluster!.id}/kubeconfig`,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Response;
		const blob = (await maybeMockBlob(
			'GET',
			`/api/v1/k3s/clusters/${activeCluster!.id}/kubeconfig`,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Blob;
		const ca = (await maybeMockBlob(
			'GET',
			`/api/v1/k3s/clusters/${activeCluster!.id}/ca-certificate`,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Blob;
		const text = await blob.text();

		expect(head.ok).toBe(true);
		expect(text).toContain('apiVersion:');
		expect(text).toContain('kind: Config');
		await expect(ca.text()).resolves.toContain('BEGIN CERTIFICATE');
		expect(fetchMock).not.toHaveBeenCalled();
	});


	it('serves lean dashboard overview contracts without changing full fixtures', async () => {
		const { maybeMockJson, maybeMockK3sStream } = await import('./transport');
		const fullSummary = await maybeMockJson<{ gpu_used: number }>(
			'GET',
			'/api/v1/dashboard/summary',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const overviewSummary = await maybeMockJson<{ recent_instances: unknown[] }>(
			'GET',
			'/api/v1/dashboard/summary?view=overview',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const overviewQuotas = await maybeMockJson<{ file_storage: unknown; alerts: unknown[] }>(
			'GET',
			'/api/v1/dashboard/quotas?view=overview',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const k3sStats = await maybeMockJson<{ total: number; active: number }>(
			'GET',
			'/api/v1/dashboard/k3s-stats',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);
		const trend = await maybeMockJson<{ network: { unit: string; data: unknown[] } }>(
			'GET',
			'/api/v1/dashboard/metrics/trend?range=14d&include_network=false',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		);

		expect(fullSummary).toMatchObject({ gpu_used: expect.any(Number) });
		expect(overviewSummary).toMatchObject({ recent_instances: expect.any(Array) });
		expect(overviewQuotas).toMatchObject({ alerts: expect.any(Array) });
		expect(k3sStats.total).toBeGreaterThanOrEqual(k3sStats.active);
		expect(trend.network).toMatchObject({ unit: 'KiB/s', data: [] });

		const clusters = (await maybeMockJson<Array<{ id: string; status: string }>>(
			'GET',
			'/api/v1/k3s/clusters',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Array<{ id: string; status: string }>;
		const deleted = clusters.find((cluster) => cluster.status === 'ACTIVE')!;
		const stream = maybeMockK3sStream(
			`/api/v1/k3s/clusters/${deleted.id}/delete-async`,
			{},
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)!;
		for await (const _event of stream) {
			// Exhaust the local mutation stream.
		}
		const afterDelete = (await maybeMockJson<{ total: number; active: number }>(
			'GET',
			'/api/v1/dashboard/k3s-stats',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as { total: number; active: number };
		expect(afterDelete.total).toBe(k3sStats.total - 1);
		expect(afterDelete.active).toBe(k3sStats.active - 1);
	});
	it('throws the exact 409 mockup error for unsupported mutations on supported pages', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockJson } = await import('./transport');
		const instances = (await maybeMockJson<Array<{ id: string }>>(
			'GET',
			'/api/v1/instances',
			undefined,
			'mock-token-tutorial-scoped',
			'mock-project-1',
		)) as Array<{ id: string }>;

		await expect(
			maybeMockJson(
				'POST',
				`/api/v1/instances/${instances[0]!.id}/floating-ip?port_id=mock-port-1`,
				{},
				'mock-token-tutorial-scoped',
				'mock-project-1',
			),
		).rejects.toMatchObject({
			status: 409,
			message: '튜토리얼 모드에서는 이 작업을 아직 지원하지 않습니다.',
		});
	});

	it('supports the volume tutorial flow: list, create, delete', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockJson } = await import('./transport');
		const list = (await maybeMockJson<Array<{ id: string; status: string }>>(
			'GET', '/api/v1/volumes', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string; status: string }>;
		expect(list.some((volume) => volume.id === 'mock-volume-1' && volume.status === 'in-use')).toBe(true);

		const created = (await maybeMockJson<{ id: string; name: string; status: string; size: number }>(
			'POST', '/api/v1/volumes', { name: 'tour-volume', size_gb: 20 }, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as { id: string; name: string; status: string; size: number };
		expect(created.name).toBe('tour-volume');
		expect(created.status).toBe('available');
		expect(created.size).toBe(20);

		const afterCreate = (await maybeMockJson<Array<{ id: string }>>(
			'GET', '/api/v1/volumes', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string }>;
		expect(afterCreate.some((volume) => volume.id === created.id)).toBe(true);

		await maybeMockJson('DELETE', `/api/v1/volumes/${created.id}`, undefined, 'mock-token-tutorial-scoped', 'mock-project-1');
		const afterDelete = (await maybeMockJson<Array<{ id: string }>>(
			'GET', '/api/v1/volumes', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string }>;
		expect(afterDelete.some((volume) => volume.id === created.id)).toBe(false);

		// 볼륨 페이지가 항상 호출하는 부속 엔드포인트도 빈 값으로 응답한다
		expect(await maybeMockJson('GET', '/api/v1/volume-snapshots', undefined, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual([]);
		expect(await maybeMockJson('POST', '/api/v1/volumes/backups/auto-backup/configs', {}, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual([]);
	});

	it('serves the VM creation wizard data fixtures', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockJson } = await import('./transport');
		const images = (await maybeMockJson<Array<{ id: string; os_distro: string }>>(
			'GET', '/api/v1/images', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string; os_distro: string }>;
		expect(images.some((image) => image.id === 'fixture-image-ubuntu' && image.os_distro === 'ubuntu')).toBe(true);

		expect(await maybeMockJson('GET', '/api/v1/libraries', undefined, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual([]);
		expect(await maybeMockJson('GET', '/api/v1/instances/availability-zones', undefined, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual([
			{ name: 'nova', available: true },
		]);
		expect(await maybeMockJson('GET', '/api/v1/networks/default', undefined, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual({
			network_id: 'mock-net-private',
		});
		expect(await maybeMockJson('GET', '/api/v1/dashboard/gpu-available', undefined, 'mock-token-tutorial-scoped', 'mock-project-1')).toEqual({ gpu_types: [] });
		const securityGroups = (await maybeMockJson<Array<{ id: string }>>(
			'GET', '/api/v1/security-groups', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string }>;
		expect(securityGroups[0]?.id).toBe('mock-sg-default');
	});

	it('streams mocked instance creation progress and appends the instance', async () => {
		// Dynamic import required: transport owns mutable singleton fixture state that each test must reinitialize.
		const { maybeMockInstanceCreateStream, maybeMockJson } = await import('./transport');
		const stream = maybeMockInstanceCreateStream('/api/v1/instances/async', {
			name: 'tour-vm',
			flavor_id: 'mock-flavor-cpu4',
			image_id: 'fixture-image-ubuntu',
		});
		expect(stream).not.toBeNull();

		const messages: Array<{ step: string; progress: number; instance_id?: string }> = [];
		for await (const message of stream!) messages.push(message);
		expect(messages.at(-1)?.step).toBe('completed');
		expect(messages.at(-1)?.progress).toBe(100);

		const instances = (await maybeMockJson<Array<{ id: string; name: string; ip_addresses: Array<{ addr: string }> }>>(
			'GET', '/api/v1/instances', undefined, 'mock-token-tutorial-scoped', 'mock-project-1',
		)) as Array<{ id: string; name: string; ip_addresses: Array<{ addr: string }> }>;
		const created = instances.find((instance) => instance.name === 'tour-vm');
		expect(created).toBeTruthy();
		expect(created!.id).toBe(messages.at(-1)?.instance_id);
		// 픽스처 주소 대역(RFC 5737) 준수
		expect(created!.ip_addresses.every((address) => address.addr.startsWith('192.0.2.'))).toBe(true);
	});
});
