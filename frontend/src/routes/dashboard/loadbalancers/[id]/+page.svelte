<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';
	import type {
		LoadBalancerDetail,
		Listener,
		Pool,
		Member,
	} from '$lib/types/resources';
	import LoadBalancerHeader from '$lib/components/dashboard/loadbalancers/id/LoadBalancerHeader.svelte';
	import LbListenerSection from '$lib/components/dashboard/loadbalancers/id/LbListenerSection.svelte';
	import LbPoolSection from '$lib/components/dashboard/loadbalancers/id/LbPoolSection.svelte';

	const id = $derived($page.params.id);

	let lb = $state<LoadBalancerDetail | null>(null);
	let listeners = $state<Listener[]>([]);
	let pools = $state<Pool[]>([]);
	let selectedPoolMembers = $state<Member[]>([]);
	let selectedPoolId = $state<string | null>(null);
	let loading = $state(true);
	let error = $state('');
	let saving = $state(false);
	let addingMember = $state(false);
	let addMemberError = $state('');
	let membersLoading = $state(false);

	async function fetchAll() {
		loading = true;
		error = '';
		await Promise.allSettled([
			api.get<LoadBalancerDetail>(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined)
				.then(v => { lb = v; loading = false; })
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

	$effect(() => { if ($auth.projectId) fetchAll(); });

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

	async function loadPoolMembers(poolId: string | null): Promise<void> {
		selectedPoolId = poolId;
	}

	async function addMember(form: { address: string; protocol_port: number; weight: number; name: string }): Promise<boolean> {
		if (!selectedPoolId) return false;
		addingMember = true;
		try {
			await api.post(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			selectedPoolMembers = await api.get<Member[]>(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			return true;
		} catch (e) {
			alert('멤버 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			return false;
		} finally {
			addingMember = false;
		}
	}

	async function removeMember(memberId: string): Promise<void> {
		if (!selectedPoolId || !confirm('멤버를 제거하시겠습니까?')) return;
		addingMember = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members/${memberId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			selectedPoolMembers = selectedPoolMembers.filter(m => m.id !== memberId);
		} catch (e) {
			alert('제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			addingMember = false;
		}
	}

	async function deleteLb() {
		if (!confirm(`로드밸런서 "${lb?.name || id}"을 삭제하시겠습니까? (연결된 리스너/풀/멤버도 모두 삭제됩니다)`)) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			saving = false;
		}
	}
</script>

<div class="max-w-4xl mx-auto px-4 py-8 text-gray-100">
	{#if loading}
		<div class="text-gray-500">불러오는 중...</div>
	{:else if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
	{:else if lb}
		<LoadBalancerHeader
			{lb}
			deleting={saving}
			onDelete={deleteLb}
		/>

		<LbListenerSection
			{listeners}
			{pools}
			{saving}
			error=""
			onAdd={createListener}
			onDelete={deleteListener}
		/>

		<LbPoolSection
			{pools}
			{selectedPoolId}
			members={selectedPoolMembers}
			{membersLoading}
			{saving}
			error=""
			{addingMember}
			{addMemberError}
			onAddPool={createPool}
			onDeletePool={deletePool}
			onSelectPool={loadPoolMembers}
			onAddMember={addMember}
			onRemoveMember={removeMember}
		/>
	{/if}
</div>
