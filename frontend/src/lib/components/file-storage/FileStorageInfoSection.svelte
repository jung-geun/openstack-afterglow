<script lang="ts">
	import { useFileStorageDetail } from '$lib/stores/fileStorageDetail.svelte';

	const s = useFileStorageDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">기본 정보</h3>
	<dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-2.5">
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">ID</dt>
			<dd class="text-sm text-gray-300 font-mono break-all">{s.fileStorage!.id}</dd>
		</div>
		<div>
			<dt class="text-xs text-gray-500 mb-0.5">크기</dt>
			<dd class="text-sm text-gray-300">{s.fileStorage!.size} GB</dd>
		</div>
		{#if s.fileStorage!.library_name}
			<div>
				<dt class="text-xs text-gray-500 mb-0.5">라이브러리</dt>
				<dd class="text-sm text-gray-300">{s.fileStorage!.library_name}</dd>
			</div>
			<div>
				<dt class="text-xs text-gray-500 mb-0.5">버전</dt>
				<dd class="text-sm text-gray-300">{s.fileStorage!.library_version ?? '-'}</dd>
			</div>
			{#if s.fileStorage!.built_at}
				<div class="col-span-2">
					<dt class="text-xs text-gray-500 mb-0.5">빌드 일시</dt>
					<dd class="text-sm text-gray-300">{s.fileStorage!.built_at}</dd>
				</div>
			{/if}
		{/if}
	</dl>
</div>
