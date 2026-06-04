<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
</script>

<div class="h-[calc(100vh-56px)] overflow-hidden flex flex-col p-4 md:p-6">
	<PageHeader breadcrumb="MONITORING / NODE" title="노드 메트릭" />
	<p class="text-xs text-gray-500 mb-2 flex-shrink-0">
		node_exporter를 통해 수집된 호스트 메트릭입니다.
	</p>
	<div class="flex-1 min-h-0">
		<GrafanaEmbed dashboardKey="node" fill />
	</div>
</div>
