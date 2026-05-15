<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="MONITORING / ETCD" title="etcd 메트릭" />

	<div class="mt-2">
		<p class="text-xs text-gray-500 mb-4">
			etcd 내장 Prometheus 엔드포인트를 통해 수집된 메트릭입니다.
		</p>
		<GrafanaEmbed dashboardKey="etcd" height={600} desktopHeight={1300} />
	</div>
</div>
