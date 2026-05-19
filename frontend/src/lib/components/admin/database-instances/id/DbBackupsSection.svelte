<script lang="ts">
	import type { DbBackup } from '$lib/types/database';

	let {
		backups,
		deletingBackup,
		restoringBackup,
		addError,
		creating,
		onAdd,
		onDelete,
		onRestore,
	}: {
		backups: DbBackup[];
		deletingBackup: string | null;
		restoringBackup: string | null;
		addError: string;
		creating: boolean;
		onAdd: (form: { name: string; description: string }) => Promise<boolean>;
		onDelete: (id: string) => Promise<void>;
		onRestore: (id: string) => Promise<void>;
	} = $props();

	let showForm = $state(false);
	let newBackup = $state({ name: '', description: '' });

	async function handleAdd() {
		const ok = await onAdd({ ...newBackup });
		if (ok) {
			showForm = false;
			newBackup = { name: '', description: '' };
		}
	}
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<div class="flex items-center justify-between mb-3">
		<h2 class="text-sm font-semibold text-white">백업</h2>
		<button onclick={() => { showForm = !showForm; }}
			class="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 px-2 py-1 rounded transition-colors">
			{showForm ? '취소' : '+ 백업 생성'}
		</button>
	</div>
	{#if showForm}
		<div class="bg-gray-800 rounded-lg p-3 mb-3 space-y-2">
			<input type="text" bind:value={newBackup.name} placeholder="backup-name"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			<input type="text" bind:value={newBackup.description} placeholder="설명 (선택)"
				class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-amber-500" />
			{#if addError}<p class="text-red-400 text-xs">{addError}</p>{/if}
			<button onclick={handleAdd} disabled={creating || !newBackup.name.trim()}
				class="text-xs bg-amber-600 hover:bg-amber-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1.5 rounded transition-colors">
				{creating ? '생성 중...' : '백업 생성'}
			</button>
		</div>
	{/if}
	{#if backups.length === 0}
		<div class="text-gray-600 text-xs">백업이 없습니다</div>
	{:else}
		<table class="w-full text-sm">
			<thead>
				<tr class="text-gray-500 text-xs">
					<th class="text-left py-2 font-medium">이름</th>
					<th class="text-left py-2 font-medium">상태</th>
					<th class="text-left py-2 font-medium">크기</th>
					<th class="text-left py-2 font-medium">생성일</th>
					<th class="text-right py-2 font-medium">액션</th>
				</tr>
			</thead>
			<tbody>
				{#each backups as b}
					<tr class="border-t border-gray-800/50">
						<td class="py-2 text-white">{b.name}</td>
						<td class="py-2 text-gray-400 text-xs">{b.status}</td>
						<td class="py-2 text-gray-400 text-xs">{b.size ? `${b.size} GB` : '-'}</td>
						<td class="py-2 text-gray-500 text-xs">{b.created_at ? b.created_at.slice(0, 10) : '-'}</td>
						<td class="py-2 text-right">
							<div class="flex justify-end gap-1">
								<button onclick={() => onRestore(b.id)} disabled={restoringBackup === b.id}
									class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-blue-900 hover:border-blue-700 transition-colors">
									{restoringBackup === b.id ? '...' : '복원'}
								</button>
								<button onclick={() => onDelete(b.id)} disabled={deletingBackup === b.id}
									class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors">
									{deletingBackup === b.id ? '...' : '삭제'}
								</button>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
</div>
