<script lang="ts">
	import { useAdminVolumeDetail } from '$lib/stores/adminVolumeDetail.svelte';

	const s = useAdminVolumeDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">연결 정보</h3>
	<div class="space-y-2">
		{#each s.volume?.attachments ?? [] as att}
			<div class="text-xs space-y-1">
				<div class="text-gray-300 font-mono">{att.server_id?.slice(0, 8)}...</div>
				<div class="text-gray-500">{att.device}</div>
			</div>
		{/each}
	</div>
</div>
