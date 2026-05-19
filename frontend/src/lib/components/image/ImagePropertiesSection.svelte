<script lang="ts">
	import { useImageDetailController, isReservedKey } from '$lib/stores/imageDetailController.svelte';

	const s = useImageDetailController();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide">
			추가 속성 <span class="normal-case font-normal text-gray-600">({Object.keys(s.image!.properties).length})</span>
		</h3>
		{#if s.canEditMetadata && !s.editingProps}
			<button onclick={() => s.startEditProps()} class="text-xs text-blue-400 hover:text-blue-300">편집</button>
		{/if}
	</div>

	{#if !s.editingProps}
		{#if Object.keys(s.image!.properties).length === 0}
			<p class="text-xs text-gray-500">추가 속성이 없습니다.</p>
		{:else}
			<table class="w-full text-xs">
				<tbody>
					{#each Object.entries(s.image!.properties) as [k, v]}
						<tr class="border-b border-gray-800/50">
							<td class="py-1.5 pr-4 text-gray-400 font-mono w-2/5">{k}</td>
							<td class="py-1.5 text-gray-300 font-mono break-all">{v}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	{:else}
		<table class="w-full text-xs mb-3">
			<tbody>
				{#each Object.entries(s.propsDraft) as [k, v]}
					<tr class="border-b border-gray-800/50">
						<td class="py-1.5 pr-2 font-mono w-2/5 {isReservedKey(k) ? 'text-gray-600' : 'text-gray-400'}">
							{k}{#if isReservedKey(k)}&nbsp;<span class="text-[10px] text-gray-600">(예약)</span>{/if}
						</td>
						<td class="py-1.5 pr-2">
							{#if isReservedKey(k)}
								<span class="text-gray-500 font-mono break-all">{v}</span>
							{:else}
								<input bind:value={s.propsDraft[k]}
									class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 font-mono text-xs focus:outline-none focus:border-blue-500" />
							{/if}
						</td>
						<td class="py-1.5 text-right w-10">
							{#if !isReservedKey(k)}
								<button onclick={() => s.removeProperty(k)} class="text-red-400 hover:text-red-300 text-xs">삭제</button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<div class="flex gap-2 mb-3">
			<input bind:value={s.newPropKey} placeholder="키"
				class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
				onkeydown={(e) => e.key === 'Enter' && s.addProperty()} />
			<input bind:value={s.newPropValue} placeholder="값"
				class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
				onkeydown={(e) => e.key === 'Enter' && s.addProperty()} />
			<button onclick={() => s.addProperty()} class="text-xs text-blue-400 hover:text-blue-300 px-2 shrink-0">+ 추가</button>
		</div>

		{#if s.propsError}
			<p class="text-red-400 text-xs mb-2">{s.propsError}</p>
		{/if}

		<div class="flex gap-2 justify-end">
			<button onclick={() => s.cancelEditProps()} disabled={s.savingProps}
				class="text-xs text-gray-400 hover:text-white px-3 py-1 border border-gray-700 rounded disabled:opacity-50">취소</button>
			<button onclick={() => s.saveProperties()} disabled={s.savingProps}
				class="text-xs text-white bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 px-3 py-1 rounded">
				{s.savingProps ? '저장 중...' : '저장'}
			</button>
		</div>
	{/if}
</div>
