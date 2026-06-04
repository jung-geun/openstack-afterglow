<script lang="ts">
	import { useDbCreate } from '$lib/stores/dbCreateStore.svelte';
	const s = useDbCreate();
</script>

<div class="space-y-3">
	<p class="text-xs text-gray-400">
		사용할 네트워크를 선택하세요. 선택하지 않으면 Trove가 기본 네트워크를 사용합니다.
	</p>
	{#if s.networks.length === 0}
		<p class="text-gray-500 text-sm">사용 가능한 네트워크가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each s.networks as net}
				<label
					class="flex items-center gap-3 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 cursor-pointer hover:border-amber-500/50 transition-colors"
				>
					<input
						type="checkbox"
						checked={s.selectedNics.includes(net.id)}
						onchange={() => s.toggleNic(net.id)}
						class="accent-amber-500"
					/>
					<span class="text-sm text-white">{net.name}</span>
					<span class="text-xs text-gray-500 font-mono">{net.id.slice(0, 8)}…</span>
				</label>
			{/each}
		</div>
	{/if}
</div>
