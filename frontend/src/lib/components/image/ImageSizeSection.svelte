<script lang="ts">
	import { useImageDetail } from '$lib/stores/imageDetail.svelte';
	import { formatSize } from '$lib/utils/format';

	const s = useImageDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
	<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">크기 정보</h3>
	<dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-3">
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">크기</dt>
			<dd class="text-sm text-gray-300">{formatSize(s.image!.size)}</dd>
		</div>
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">가상 크기</dt>
			<dd class="text-sm text-gray-300">{formatSize(s.image!.virtual_size)}</dd>
		</div>
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">최소 디스크</dt>
			<dd class="text-sm text-gray-300">{s.image!.min_disk} GB</dd>
		</div>
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">최소 RAM</dt>
			<dd class="text-sm text-gray-300">{s.image!.min_ram} MB</dd>
		</div>
	</dl>
</div>
