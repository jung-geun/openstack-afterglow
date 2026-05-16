<script lang="ts">
	import { useImageDetail } from '$lib/stores/imageDetail.svelte';
	import { formatIsoDateTime } from '$lib/utils/format';

	const s = useImageDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
	<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">메타데이터</h3>
	<dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-3">
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">등록일</dt>
			<dd class="text-sm text-gray-300">{formatIsoDateTime(s.image!.created_at)}</dd>
		</div>
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">수정일</dt>
			<dd class="text-sm text-gray-300">{formatIsoDateTime(s.image!.updated_at)}</dd>
		</div>
		{#if s.image!.checksum}
			<div class="col-span-2">
				<dt class="text-xs text-gray-500 mb-0.5">체크섬 (MD5)</dt>
				<dd class="text-xs text-gray-300 font-mono break-all">{s.image!.checksum}</dd>
			</div>
		{/if}
	</dl>
</div>
