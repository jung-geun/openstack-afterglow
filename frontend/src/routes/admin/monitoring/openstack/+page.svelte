<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="MONITORING / OPENSTACK" title="OpenStack 메트릭" />

	<div class="mt-2">
		<p class="text-xs text-gray-500 mb-4">
			openstack_exporter 를 통해 수집된 클러스터 서비스 상태 및 자원 사용 현황입니다.
		</p>
		<GrafanaEmbed dashboardKey="openstack" height={600} desktopHeight={1400} />
	</div>
</div>
