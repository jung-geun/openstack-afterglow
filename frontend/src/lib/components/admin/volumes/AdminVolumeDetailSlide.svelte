<script lang="ts">
	import SlidePanel from '$lib/components/SlidePanel.svelte';

	let {
		volumeId,
		token,
		projectId,
		onClose,
		onRefresh,
	}: {
		volumeId: string;
		token?: string;
		projectId?: string;
		onClose: () => void;
		onRefresh: () => void;
	} = $props();
</script>

<SlidePanel {onClose} width="w-full md:w-[50vw] max-w-2xl" dataTour="admin-storage-detail">
	{#await import('$lib/components/AdminVolumeDetailPanel.svelte') then { default: Panel }}
		<Panel {volumeId} {onClose} {onRefresh} {token} {projectId} />
	{:catch}
		<div class="p-6">
			<a href="/admin/volumes/{volumeId}" class="text-blue-400 hover:text-blue-300">상세 페이지에서 보기 →</a>
		</div>
	{/await}
</SlidePanel>
