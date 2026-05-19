<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

	let data = $state<Record<string, unknown> | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let period = $state<'24h' | '7d' | '30d'>('7d');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function fetchData() {
		if (!token || !projectId) return;
		loading = !data;
		error = null;
		try {
			const res = await api.get(`/api/dashboard/usage-stats?range=${period}`, token, projectId);
			data = res as Record<string, unknown>;
		} catch (e) {
			error = e instanceof Error ? e.message : '데이터 로딩 실패';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void [token, projectId, period];
		fetchData();
	});

	const ar = createAutoRefresh(fetchData, {
		storageKey: 'dashboard-usage',
		defaultActive: true,
		defaultInterval: 60,
		invokeOnMount: false,
	});
</script>

<div class="p-6 space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-xl font-semibold text-white">사용량</h1>
		<div class="flex items-center gap-2">
			{#each (['24h', '7d', '30d'] as const) as p}
				<button
					onclick={() => period = p}
					class="px-3 py-1.5 rounded-lg text-xs transition-colors {period === p ? 'bg-[var(--color-warm)] text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
				>{p}</button>
			{/each}
			<button
				onclick={() => ar.active = !ar.active}
				class="px-3 py-1.5 rounded-lg text-xs transition-colors {ar.active ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
				title="자동 새로고침"
			>↻</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-400 text-sm">로딩 중...</div>
	{:else if error}
		<div class="text-red-400 text-sm">{error}</div>
	{:else if data}
		<pre class="bg-gray-900 border border-gray-800 rounded-2xl p-5 text-xs text-gray-300 overflow-auto">{JSON.stringify(data, null, 2)}</pre>
	{/if}
</div>
