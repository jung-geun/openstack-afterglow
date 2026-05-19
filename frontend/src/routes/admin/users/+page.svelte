<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { User, PagedResponse } from '$lib/types/common';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import AdminUsersTable from '$lib/components/admin/users/AdminUsersTable.svelte';
	import AdminUserCreateModal from '$lib/components/admin/users/AdminUserCreateModal.svelte';
	import AdminUserEditModal from '$lib/components/admin/users/AdminUserEditModal.svelte';

	let users = $state<User[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let showCreate = $state(false);
	let editUser = $state<User | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		if (users.length === 0) loading = true;
		else refreshing = true;
		try {
			let url = `/api/admin/users?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<User>>(url, token, projectId);
			users = res.items;
			nextMarker = res.next_marker;
		} catch { users = []; } finally { loading = false; refreshing = false; }
	}

	async function create(form: { name: string; email: string; password: string; enabled: boolean }): Promise<string | true> {
		try {
			await api.post('/api/admin/users', {
				name: form.name, email: form.email || null, password: form.password || null, enabled: form.enabled,
			}, token, projectId);
			await load();
			return true;
		} catch (e) { return e instanceof ApiError ? e.message : '생성 실패'; }
	}

	async function update(id: string, form: { name: string; email: string; password: string; enabled: boolean }): Promise<string | true> {
		try {
			await api.patch(`/api/admin/users/${id}`, {
				name: form.name, email: form.email || null, enabled: form.enabled,
				...(form.password ? { password: form.password } : {}),
			}, token, projectId);
			await load();
			return true;
		} catch (e) { return e instanceof ApiError ? e.message : '수정 실패'; }
	}

	function autoRefreshLoad() { load(markerStack[markerStack.length - 1]); }

	const ar = createAutoRefresh(autoRefreshLoad, {
		storageKey: 'admin-users',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [30, 60]
	});

	onMount(load);
</script>

<AdminUserCreateModal bind:open={showCreate} onCreate={create} />
<AdminUserEditModal bind:user={editUser} onUpdate={update} />

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / USERS" title="사용자">
		{#snippet actions()}
			<button onclick={() => { showCreate = true; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={() => load()}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}">{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<AdminUsersTable
			{users}
			{refreshing}
			hasPrev={markerStack.length > 0}
			hasNext={nextMarker !== null}
			onEdit={(u) => { editUser = u; }}
			onPrev={() => { const prev = markerStack.slice(0, -1); markerStack = prev; load(prev[prev.length - 1]); }}
			onNext={() => { if (nextMarker) { markerStack = [...markerStack, nextMarker]; load(nextMarker); } }}
		/>
	{/if}
</div>
