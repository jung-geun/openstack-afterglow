<script lang="ts">
	import { useDbInstanceDetailController } from '$lib/stores/dbInstanceDetailController.svelte';

	const s = useDbInstanceDetailController();

	let showDbForm = $state(false);
	let newDbName = $state('');

	async function handleCreateDb() {
		if (!newDbName.trim()) return;
		const ok = await s.createDb(newDbName.trim());
		if (ok) {
			showDbForm = false;
			newDbName = '';
		}
	}
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<div class="flex items-center justify-between mb-3">
		<h2 class="text-sm font-semibold text-white">데이터베이스</h2>
		<button onclick={() => { showDbForm = !showDbForm; s.dbError = ''; }}
			class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
			{showDbForm ? '취소' : '+ 추가'}
		</button>
	</div>
	{#if showDbForm}
		<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
			<input type="text" bind:value={newDbName} placeholder="database_name"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			{#if s.dbError}<p class="text-red-400 text-xs">{s.dbError}</p>{/if}
			<button onclick={handleCreateDb} disabled={s.creatingDb || !newDbName.trim()}
				class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
				{s.creatingDb ? '생성 중...' : '생성'}
			</button>
		</div>
	{/if}
	{#if s.databases.length === 0}
		<div class="text-gray-600 text-xs">데이터베이스가 없습니다</div>
	{:else}
		<div class="space-y-1">
			{#each s.databases as db}
				<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50">
					<span class="text-white text-sm font-medium">{db.name}</span>
					<button onclick={() => s.deleteDb(db.name)} disabled={s.deletingDb === db.name}
						class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
						{s.deletingDb === db.name ? '...' : '삭제'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
