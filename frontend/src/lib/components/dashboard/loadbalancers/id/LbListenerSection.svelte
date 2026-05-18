<script lang="ts">
	import type { Listener, Pool } from '$lib/types/resources';

	let {
		listeners,
		pools,
		saving,
		error,
		onAdd,
		onDelete,
	}: {
		listeners: Listener[];
		pools: Pool[];
		saving: boolean;
		error: string;
		onAdd: (form: { protocol: string; protocol_port: number; name: string }) => Promise<boolean>;
		onDelete: (id: string) => Promise<void>;
	} = $props();

	let showAddListener = $state(false);
	let listenerForm = $state({ protocol: 'HTTP', protocol_port: 80, name: '' });

	async function handleAdd() {
		const ok = await onAdd(listenerForm);
		if (ok) {
			showAddListener = false;
			listenerForm = { protocol: 'HTTP', protocol_port: 80, name: '' };
		}
	}
</script>

<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<div class="flex items-center justify-between mb-4">
		<h2 class="font-semibold text-white">리스너 ({listeners.length})</h2>
		<button onclick={() => showAddListener = !showAddListener} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 추가</button>
	</div>

	{#if showAddListener}
		<div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg grid grid-cols-1 sm:grid-cols-3 gap-2">
			<input bind:value={listenerForm.name} placeholder="이름 (선택)" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
			<select bind:value={listenerForm.protocol} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
				{#each ['HTTP', 'HTTPS', 'TCP', 'UDP'] as p}
					<option value={p}>{p}</option>
				{/each}
			</select>
			<input bind:value={listenerForm.protocol_port} type="number" min="1" max="65535" placeholder="포트" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
			<button onclick={handleAdd} disabled={saving} class="col-span-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">생성</button>
			<button onclick={() => showAddListener = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center">취소</button>
		</div>
	{/if}

	{#if listeners.length === 0}
		<p class="text-sm text-gray-600">리스너가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each listeners as l}
				<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-3">
					<div class="text-sm">
						<span class="text-white font-medium">{l.name || l.id.slice(0, 10)}</span>
						<span class="ml-2 text-xs text-blue-300 bg-blue-900/30 px-1.5 py-0.5 rounded">{l.protocol}:{l.protocol_port}</span>
						<span class="ml-2 text-xs {l.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{l.status}</span>
					</div>
					<button onclick={() => onDelete(l.id)} disabled={saving} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors">삭제</button>
				</div>
			{/each}
		</div>
	{/if}
</section>
