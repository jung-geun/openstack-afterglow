import { getContext, setContext } from 'svelte';
import { untrack } from 'svelte';
import { goto } from '$app/navigation';
import { api, ApiError } from '$lib/api/client';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import type { RouterDetail } from '$lib/types/router';
import type { SubnetDetail } from '$lib/types/networks';
import type { Network } from '$lib/types/resources';

interface Options {
	routerId: () => string;
	token: () => string | undefined;
	projectId: () => string | undefined;
	onDeleted?: () => void;
	onClose?: () => void;
}

function createRouterDetailStore(opts: Options) {
	let router = $state<RouterDetail | null>(null);
	let loading = $state(true);
	let error = $state('');
	let saving = $state(false);

	let availableNetworks = $state<Network[]>([]);
	let externalNetworks = $state<Network[]>([]);
	let allSubnets = $state<SubnetDetail[]>([]);

	let showAddInterface = $state(false);
	let selectedNetId = $state('');
	let selectedSubnetId = $state('');
	let showSetGateway = $state(false);
	let selectedExtNetId = $state('');

	const canAddInterface = $derived(!!selectedSubnetId && !saving);

	$effect(() => {
		const netId = selectedNetId;
		if (!netId) {
			allSubnets = [];
			selectedSubnetId = '';
			return;
		}
		const tok = untrack(() => opts.token());
		const proj = untrack(() => opts.projectId());
		api.get<{ subnet_details: SubnetDetail[] }>(`/api/networks/${netId}`, tok, proj)
			.then(d => {
				allSubnets = d.subnet_details ?? [];
				selectedSubnetId = allSubnets[0]?.id ?? '';
			})
			.catch(() => {});
	});

	async function fetchRouter() {
		loading = true;
		error = '';
		try {
			router = await api.get<RouterDetail>(`/api/routers/${opts.routerId()}`, opts.token(), opts.projectId());
		} catch (e) {
			error = e instanceof ApiError ? e.message : '라우터 조회 실패';
		} finally {
			loading = false;
		}
	}

	async function fetchNetworks() {
		try {
			const nets = await api.get<Network[]>('/api/networks', opts.token(), opts.projectId());
			availableNetworks = nets.filter(n => !n.is_external);
			externalNetworks = nets.filter(n => n.is_external);
		} catch { /* 무시 */ }
	}

	async function addInterface() {
		if (!selectedSubnetId) return;
		saving = true;
		try {
			await api.post(`/api/routers/${opts.routerId()}/interfaces`, { subnet_id: selectedSubnetId }, opts.token(), opts.projectId());
			showAddInterface = false;
			selectedNetId = '';
			selectedSubnetId = '';
			await fetchRouter();
		} catch (e) {
			alert('인터페이스 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function removeInterface(subnetId: string) {
		if (!(await confirmDialog('인터페이스를 제거하시겠습니까?'))) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${opts.routerId()}/interfaces/${subnetId}`, opts.token(), opts.projectId());
			await fetchRouter();
		} catch (e) {
			alert('인터페이스 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function setGateway() {
		if (!selectedExtNetId) return;
		saving = true;
		try {
			await api.post(`/api/routers/${opts.routerId()}/gateway`, { external_network_id: selectedExtNetId }, opts.token(), opts.projectId());
			showSetGateway = false;
			selectedExtNetId = '';
			await fetchRouter();
		} catch (e) {
			alert('게이트웨이 설정 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function removeGateway() {
		if (!(await confirmDialog('외부 게이트웨이를 제거하시겠습니까?'))) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${opts.routerId()}/gateway`, opts.token(), opts.projectId());
			await fetchRouter();
		} catch (e) {
			alert('게이트웨이 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deleteRouter() {
		if (!(await confirmDialog(`라우터 "${router?.name || opts.routerId()}"을 삭제하시겠습니까?`))) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${opts.routerId()}`, opts.token(), opts.projectId());
			if (opts.onDeleted) {
				opts.onDeleted();
			} else {
				opts.onClose?.();
				goto('/dashboard/network/routers');
			}
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			saving = false;
		}
	}

	return {
		get router() { return router; },
		get loading() { return loading; },
		get error() { return error; },
		get saving() { return saving; },
		get availableNetworks() { return availableNetworks; },
		get externalNetworks() { return externalNetworks; },
		get allSubnets() { return allSubnets; },
		get showAddInterface() { return showAddInterface; },
		set showAddInterface(v: boolean) { showAddInterface = v; },
		get selectedNetId() { return selectedNetId; },
		set selectedNetId(v: string) { selectedNetId = v; },
		get selectedSubnetId() { return selectedSubnetId; },
		set selectedSubnetId(v: string) { selectedSubnetId = v; },
		get showSetGateway() { return showSetGateway; },
		set showSetGateway(v: boolean) { showSetGateway = v; },
		get selectedExtNetId() { return selectedExtNetId; },
		set selectedExtNetId(v: string) { selectedExtNetId = v; },
		get canAddInterface() { return canAddInterface; },
		fetchRouter,
		fetchNetworks,
		addInterface,
		removeInterface,
		setGateway,
		removeGateway,
		deleteRouter,
	};
}

export type RouterDetailStore = ReturnType<typeof createRouterDetailStore>;
export { createRouterDetailStore };

const ROUTER_DETAIL_KEY = Symbol('router-detail');

export function provideRouterDetail(store: RouterDetailStore) {
	setContext(ROUTER_DETAIL_KEY, store);
}

export function useRouterDetail(): RouterDetailStore {
	const store = getContext<RouterDetailStore | undefined>(ROUTER_DETAIL_KEY);
	if (!store) throw new Error('useRouterDetail must be called within RouterDetailPanel');
	return store;
}
