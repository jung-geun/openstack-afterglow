<script lang="ts">
	import { projectNames } from '$lib/stores/projectNames';
	import { useAdminVolumeDetail } from '$lib/stores/adminVolumeDetail.svelte';

	const s = useAdminVolumeDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
	<dl class="space-y-2 text-xs">
		<div class="flex justify-between">
			<dt class="text-gray-400">ID</dt>
			<dd class="text-gray-300 font-mono text-xs">{s.volume?.id}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">볼륨 유형</dt>
			<dd class="text-gray-300">{s.volume?.volume_type || '-'}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">프로젝트</dt>
			<dd class="text-gray-300">
				{s.volume?.project_id ? ($projectNames.get(s.volume.project_id) ?? s.volume.project_id.slice(0, 8)) : '-'}
			</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">생성일</dt>
			<dd class="text-gray-300">{s.volume?.created_at?.slice(0, 19) ?? '-'}</dd>
		</div>
		{#if s.volume?.description}
			<div class="flex justify-between">
				<dt class="text-gray-400">설명</dt>
				<dd class="text-gray-300">{s.volume.description}</dd>
			</div>
		{/if}
	</dl>
</div>
