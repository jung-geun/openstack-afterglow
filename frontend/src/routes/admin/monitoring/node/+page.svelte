<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="MONITORING / NODE" title="노드 메트릭" />

	<div class="mt-2">
		<p class="text-xs text-gray-500 mb-4">
			node_exporter를 통해 수집된 호스트 메트릭입니다.
		</p>
		<GrafanaEmbed dashboardKey="node" height={600} desktopHeight={1400} />
	</div>
</div>
