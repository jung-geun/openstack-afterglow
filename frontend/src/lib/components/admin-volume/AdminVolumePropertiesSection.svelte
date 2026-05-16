<script lang="ts">
	import { useAdminVolumeDetail } from '$lib/stores/adminVolumeDetail.svelte';

	const s = useAdminVolumeDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">속성</h3>
	<dl class="space-y-2 text-xs">
		<div class="flex justify-between">
			<dt class="text-gray-400">부트 가능</dt>
			<dd class="{s.volume?.bootable ? 'text-green-400' : 'text-gray-500'}">{s.volume?.bootable ? '예' : '아니오'}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">암호화</dt>
			<dd class="{s.volume?.encrypted ? 'text-yellow-400' : 'text-gray-500'}">{s.volume?.encrypted ? '예' : '아니오'}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">다중 연결</dt>
			<dd class="{s.volume?.multiattach ? 'text-blue-400' : 'text-gray-500'}">{s.volume?.multiattach ? '예' : '아니오'}</dd>
		</div>
	</dl>
</div>
