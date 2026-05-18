<script lang="ts">
	import type { K3sClusterTemplate } from '$lib/types/k3s';

	let {
		template,
		onEdit,
		onDelete,
	}: {
		template: K3sClusterTemplate;
		onEdit: (t: K3sClusterTemplate) => void;
		onDelete: (t: K3sClusterTemplate) => void;
	} = $props();
</script>

<div class="bg-gray-900 border border-gray-700 rounded-xl p-4 flex flex-col gap-3">
	<div class="flex items-start justify-between gap-2">
		<div class="min-w-0">
			<div class="flex items-center gap-2">
				<span class="font-semibold text-white text-sm truncate">{template.name}</span>
				{#if !template.public_visible}
					<span class="px-1.5 py-0.5 bg-gray-700 text-gray-400 text-xs rounded">비공개</span>
				{/if}
			</div>
			{#if template.description}
				<p class="text-xs text-gray-400 mt-0.5 truncate">{template.description}</p>
			{/if}
		</div>
		<div class="flex gap-1 shrink-0">
			<button
				onclick={() => onEdit(template)}
				class="px-2 py-1 text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded"
			>수정</button>
			<button
				onclick={() => onDelete(template)}
				class="px-2 py-1 text-xs text-red-400 hover:text-red-300 bg-gray-800 hover:bg-gray-700 rounded"
			>삭제</button>
		</div>
	</div>

	<div class="grid grid-cols-2 gap-2 text-xs">
		<div class="text-gray-500">k3s 버전</div>
		<div class="text-gray-300 font-mono">{template.k3s_version ?? '설정값'}</div>
		<div class="text-gray-500">에이전트 수</div>
		<div class="text-gray-300">{template.default_node_count}대</div>
		<div class="text-gray-500">OS</div>
		<div class="text-gray-300">{template.os_type}</div>
		<div class="text-gray-500">플러그인</div>
		<div class="text-gray-300">
			{#if Object.keys(template.plugins_enabled).length === 0}
				없음
			{:else}
				{Object.entries(template.plugins_enabled).filter(([, v]) => v).map(([k]) => k).join(', ') || '없음'}
			{/if}
		</div>
	</div>
</div>
