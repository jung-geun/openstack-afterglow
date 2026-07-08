import { getContext, setContext } from 'svelte';
import { api, ApiError } from '$lib/api/client';
import type { NetworkDetail, NetworkRouterInfo, RouterListItem } from '$lib/types/networks';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';

interface Options {
	networkId: () => string;
	apiBase: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	onClose?: () => void;
}

function createNetworkDetailController(opts: Options) {
	let network = $state<NetworkDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	let allRouters = $state<RouterListItem[]>([]);
	let showRouterConnect = $state(false);
	let selectedRouterId = $state('');
	let selectedSubnetId = $state('');
	let connectingRouter = $state(false);

	const isUserPanel = $derived(opts.apiBase() === '/api/v1/networks');

	$effect(() => {
		const id = opts.networkId();
		if (!id) return;
		loading = true;
		error = '';
		network = null;
		showRouterConnect = false;
		fetchNetwork();
	});

	async function fetchNetwork() {
		try {
			network = await api.get<NetworkDetail>(`${opts.apiBase()}/${opts.networkId()}`, opts.token(), opts.projectId());
		} catch (e) {
			error = e instanceof ApiError ? e.message : '네트워크 조회 실패';
		} finally {
			loading = false;
		}
	}

	async function openRouterConnect() {
		if (!allRouters.length) {
			try {
				allRouters = await api.get<RouterListItem[]>('/api/v1/routers', opts.token(), opts.projectId());
			} catch {
				allRouters = [];
			}
		}
		selectedRouterId = allRouters[0]?.id ?? '';
		selectedSubnetId = network?.subnet_details[0]?.id ?? '';
		showRouterConnect = true;
	}

	async function connectRouter() {
		if (!selectedRouterId || !selectedSubnetId) return;
		connectingRouter = true;
		try {
			const subnet = network?.subnet_details.find(s => s.id === selectedSubnetId);
			const autoGateway = !subnet?.gateway_ip;
			await api.post(
				`/api/v1/routers/${selectedRouterId}/interfaces`,
				{ subnet_id: selectedSubnetId, auto_gateway: autoGateway },
				opts.token(),
				opts.projectId()
			);
			showRouterConnect = false;
			await fetchNetwork();
		} catch (e) {
			toast.error('라우터 연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			connectingRouter = false;
		}
	}

	async function disconnectRouter(router: NetworkRouterInfo) {
		const subnetIds = network?.subnet_details.map(s => s.id) ?? [];
		const targetSubnet = router.connected_subnet_ids.find(sid => subnetIds.includes(sid));
		if (!targetSubnet) {
			toast.warning('연결된 서브넷을 찾을 수 없습니다.');
			return;
		}
		if (!(await confirmDialog(`라우터 "${router.name || router.id.slice(0, 8)}"과의 연결을 해제하시겠습니까?`))) return;
		try {
			await api.delete(`/api/v1/routers/${router.id}/interfaces/${targetSubnet}`, opts.token(), opts.projectId());
			await fetchNetwork();
		} catch (e) {
			toast.error('라우터 연결 해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	return {
		get network() { return network; },
		get loading() { return loading; },
		get error() { return error; },
		get isUserPanel() { return isUserPanel; },
		get allRouters() { return allRouters; },
		get showRouterConnect() { return showRouterConnect; },
		set showRouterConnect(v: boolean) { showRouterConnect = v; },
		get selectedRouterId() { return selectedRouterId; },
		set selectedRouterId(v: string) { selectedRouterId = v; },
		get selectedSubnetId() { return selectedSubnetId; },
		set selectedSubnetId(v: string) { selectedSubnetId = v; },
		get connectingRouter() { return connectingRouter; },
		fetchNetwork,
		openRouterConnect,
		connectRouter,
		disconnectRouter,
	};
}

export type NetworkDetailController = ReturnType<typeof createNetworkDetailController>;
export { createNetworkDetailController };

const NETWORK_DETAIL_KEY = Symbol('network-detail');

export function provideNetworkDetailController(store: NetworkDetailController) {
	setContext(NETWORK_DETAIL_KEY, store);
}

export function useNetworkDetailController(): NetworkDetailController {
	const store = getContext<NetworkDetailController | undefined>(NETWORK_DETAIL_KEY);
	if (!store) throw new Error('useNetworkDetailController must be called within NetworkDetailPanel');
	return store;
}
