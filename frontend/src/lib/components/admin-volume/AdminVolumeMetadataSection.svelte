<script lang="ts">
	import { useAdminVolumeDetailController } from '$lib/stores/adminVolumeDetailController.svelte';

	const s = useAdminVolumeDetailController();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">메타데이터</h3>
	<dl class="space-y-1.5 text-xs">
		{#each Object.entries(s.volume?.metadata ?? {}) as [k, v]}
			<div class="flex gap-2">
				<dt class="text-gray-500 min-w-24">{k}</dt>
				<dd class="text-gray-300 break-all">{v}</dd>
			</div>
		{/each}
	</dl>
</div>
