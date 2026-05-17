<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import LbDetailHeader from '$lib/components/dashboard/loadbalancers/LbDetailHeader.svelte';
	import LbErrorStatusTree from '$lib/components/dashboard/loadbalancers/LbErrorStatusTree.svelte';
	import ListenerSection from '$lib/components/dashboard/loadbalancers/ListenerSection.svelte';
	import PoolSection from '$lib/components/dashboard/loadbalancers/PoolSection.svelte';
	import type {
		LoadBalancerDetail,
		Listener,
		Pool,
		Member,
		LbStatusNode,
	} from '$lib/types/resources';

	const id = $derived($page.params.id);

	let lb = $state<LoadBalancerDetail | null>(null);
	let listeners = $state<Listener[]>([]);
	let pools = $state<Pool[]>([]);
	let selectedPoolMembers = $state<Member[]>([]);
	let selectedPoolId = $state<string | null>(null);
	let loading = $state(true);
	let error = $state('');
	let saving = $state(false);

	let statusTree = $state<LbStatusNode | null>(null);

	async function fetchAll() {
		loading = true;
		error = '';
		await Promise.allSettled([
			api.get<LoadBalancerDetail>(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined)
				.then(v => {
					lb = v;
					loading = false;
					if (v.status === 'ERROR') {
						api.get<LbStatusNode>(`/api/loadbalancers/${id}/status`, $auth.token ?? undefined, $auth.projectId ?? undefined)
							.then(tree => { statusTree = tree; })
							.catch(() => {});
					}
				})
				.catch(e => { error = e instanceof ApiError ? e.message : '조회 실패'; loading = false; }),
			api.get<Listener[]>(`/api/loadbalancers/${id}/listeners`, $auth.token ?? undefined, $auth.projectId ?? undefined)
				.then(v => { listeners = v; })
				.catch(() => {}),
			api.get<Pool[]>(`/api/loadbalancers/${id}/pools`, $auth.token ?? undefined, $auth.projectId ?? undefined)
				.then(v => { pools = v; })
				.catch(() => {}),
		]);
		loading = false;
	}

	const ar = createAutoRefresh(() => fetchAll(), {
		storageKey: 'dashboard-network-lb-detail',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => { if ($auth.projectId) untrack(() => fetchAll()); });

	$effect(() => {
		if (!selectedPoolId) { selectedPoolMembers = []; return; }
		api.get<Member[]>(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined)
			.then(m => { selectedPoolMembers = m; })
			.catch(() => {});
	});

	async function createListener(form: { protocol: string; protocol_port: number; name: string }): Promise<boolean> {
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/listeners`, form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchAll();
			return true;
		} catch (e) {
			alert('리스너 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			return false;
		} finally {
			saving = false;
		}
	}

	async function deleteListener(listenerId: string): Promise<void> {
		if (!confirm('리스너를 삭제하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/listeners/${listenerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchAll();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function createPool(form: { protocol: string; lb_algorithm: string; name: string }): Promise<boolean> {
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/pools`, form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchAll();
			return true;
		} catch (e) {
			alert('풀 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			return false;
		} finally {
			saving = false;
		}
	}

	async function deletePool(poolId: string): Promise<void> {
		if (!confirm('풀을 삭제하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/pools/${poolId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			if (selectedPoolId === poolId) selectedPoolId = null;
			await fetchAll();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function addMember(form: { address: string; protocol_port: number; weight: number; name: string }): Promise<boolean> {
		if (!selectedPoolId) return false;
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			selectedPoolMembers = await api.get<Member[]>(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			return true;
		} catch (e) {
			alert('멤버 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			return false;
		} finally {
			saving = false;
		}
	}

	async function removeMember(memberId: string): Promise<void> {
		if (!selectedPoolId || !confirm('멤버를 제거하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members/${memberId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			selectedPoolMembers = selectedPoolMembers.filter(m => m.id !== memberId);
		} catch (e) {
			alert('제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deleteLb() {
		if (!confirm(`로드밸런서 "${lb?.name || id}"을 삭제하시겠습니까? (연결된 리스너/풀/멤버도 모두 삭제됩니다)`)) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard/network/loadbalancers');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			saving = false;
		}
	}
</script>

<div class="max-w-4xl mx-auto px-4 py-8 text-gray-100">
	<div class="flex items-center justify-between mb-6">
		<button onclick={() => goto('/dashboard/network/loadbalancers')} class="text-sm text-gray-400 hover:text-gray-200 inline-flex items-center gap-1">
			← 로드밸런서 목록
		</button>
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={loading}
			onManualRefresh={() => fetchAll()}
		/>
	</div>

	{#if loading}
		<div class="text-gray-500">불러오는 중...</div>
	{:else if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
	{:else if lb}
		<LbDetailHeader {lb} {saving} onDelete={deleteLb} />

		{#if lb.status === 'ERROR' || lb.status?.includes('ERROR')}
			<LbErrorStatusTree {lb} {statusTree} />
		{/if}

		<ListenerSection
			{listeners}
			{saving}
			onCreate={createListener}
			onDelete={deleteListener}
		/>

		<PoolSection
			{pools}
			members={selectedPoolMembers}
			{saving}
			bind:selectedPoolId
			onCreatePool={createPool}
			onDeletePool={deletePool}
			onAddMember={addMember}
			onRemoveMember={removeMember}
		/>
	{/if}
</div>
