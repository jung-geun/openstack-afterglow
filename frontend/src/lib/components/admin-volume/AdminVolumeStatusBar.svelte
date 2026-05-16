<script lang="ts">
	import { useAdminVolumeDetail } from '$lib/stores/adminVolumeDetail.svelte';

	const s = useAdminVolumeDetail();

	const statusColor: Record<string, string> = {
		available: 'text-green-400',
		creating: 'text-yellow-400',
		error: 'text-red-400',
		in_use: 'text-blue-400',
		deleting: 'text-red-400',
	};
</script>

<div class="flex items-center gap-3">
	<span class="text-lg font-semibold text-white">{s.volume?.name || '-'}</span>
	<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[s.volume?.status ?? ''] ?? 'text-gray-400'}">{s.volume?.status}</span>
	<span class="text-gray-400 text-sm">{s.volume?.size} GB</span>
</div>
